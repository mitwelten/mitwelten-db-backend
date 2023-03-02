from api.config import crd
from api.database import database
from api.models import QueueInputDefinition, QueueUpdateDefinition
from api.tables import birdnet_input, tasks

from fastapi import APIRouter
from sqlalchemy.sql import insert, func, select, text
from sqlalchemy.sql.functions import current_timestamp

router = APIRouter()

# ------------------------------------------------------------------------------
# QUEUE MANAGER
# ------------------------------------------------------------------------------

@router.get('/queue/progress/', tags=['queue'])
async def read_progress():
    query = select(birdnet_input.c.node_label, tasks.c.state,
            func.sum(birdnet_input.c.file_size).label('size'),
            func.count(birdnet_input.c.file_id).label('count')).\
        outerjoin(tasks).\
        where(birdnet_input.c.sample_rate == 48000, birdnet_input.c.duration >= 3).\
        group_by(tasks.c.state, birdnet_input.c.node_label).\
        order_by(birdnet_input.c.node_label)
    progess = await database.fetch_all(query)
    node_progress = {}
    for row in progess:
        if row.node_label not in node_progress:
            node_progress[row.node_label] = {
                'size': 0,
                'total_count': 0,
                'total_pending': 0,

                'noqueue': 0,  # None
                'pending': 0,  # 0
                'running': 0,  # 1
                'complete': 0, # 2
                'failed': 0,   # 3
                'paused': 0,   # 4
            }

        node_progress[row.node_label]['size']  += row['size']
        node_progress[row.node_label]['total_count']  += row['count']

        if row.state != 2:
            node_progress[row.node_label]['total_pending']  += row['count']

        if row.state == None:
            node_progress[row.node_label]['noqueue']  = row['count']
        elif row.state == 0:
            node_progress[row.node_label]['pending']  = row['count']
        elif row.state == 1:
            node_progress[row.node_label]['running']  = row['count']
        elif row.state == 2:
            node_progress[row.node_label]['complete'] = row['count']
        elif row.state == 3:
            node_progress[row.node_label]['failed']   = row['count']
        elif row.state == 4:
            node_progress[row.node_label]['paused']   = row['count']

    return list(map(lambda i: {'node_label': i[0], **i[1]}, node_progress.items()))

@router.get('/queue/input/', tags=['queue'])
async def read_input():
    query = f'''
    select node_label, count(node_label) as count, min(time) as date_start, max(time) as date_end, sum(file_size) as size
    from {crd.db.schema}.birdnet_input
    group by node_label
    '''
    return await database.execute(query).fetchall()

@router.post('/queue/input/', tags=['queue'])
async def queue_input(definition: QueueInputDefinition):

    select_query = select(birdnet_input.c.file_id, 1, 0, current_timestamp()).\
        outerjoin(tasks).\
        where(birdnet_input.c.sample_rate == 48000, birdnet_input.c.duration >= 3,
            tasks.c.state == None, birdnet_input.c.node_label == definition.node_label)
    insert_query = insert(tasks).from_select(['file_id', 'config_id', 'state', 'scheduled_on'], select_query)
    # 'on conflict do nothing' not implemented.
    # not required here as the records are selected by the fact that they are absent.

    return await database.execute(insert_query)

@router.patch('/queue/input/', tags=['queue'])
async def queue_input(definition: QueueUpdateDefinition):

    transition_query = text(f'''
    update {crd.db.schema}.birdnet_tasks set state = :to_state
    where task_id in (
        select task_id from {crd.db.schema}.birdnet_tasks t
        left outer join {crd.db.schema}.birdnet_input i on i.file_id = t.file_id
        where t.state = :from_state and node_label = :node_label
        for update of t skip locked
    )
    ''')

    reset_query = text(f'''
    update {crd.db.schema}.birdnet_tasks set state = 0
    where task_id in (
        select task_id from {crd.db.schema}.birdnet_tasks t
        left outer join {crd.db.schema}.birdnet_input i on i.file_id = t.file_id
        where node_label = :node_label
        for update of t skip locked
    )
    ''')

    delete_failed_results_query = text(f'''
    delete from {crd.db.schema}.birdnet_results
    where task_id in (
        select task_id from {crd.db.schema}.birdnet_tasks t
        left outer join {crd.db.schema}.birdnet_input i on i.file_id = t.file_id
        where t.state = 3 and node_label = :node_label
    )
    ''')

    delete_results_query = text(f'''
    delete from {crd.db.schema}.birdnet_results
    where task_id in (
        select task_id from {crd.db.schema}.birdnet_tasks t
        left outer join {crd.db.schema}.birdnet_input i on i.file_id = t.file_id
        where node_label = :node_label
    )
    ''')

    if definition.action == 'pause':
        return await database.execute(transition_query.bindparams(from_state=0, to_state=4, node_label=definition.node_label))
    elif definition.action == 'resume':
        return await database.execute(transition_query.bindparams(from_state=4, to_state=0, node_label=definition.node_label))
    elif definition.action == 'reset_failed':
        await database.execute(delete_failed_results_query.bindparams(node_label=definition.node_label))
        return await database.execute(transition_query.bindparams(from_state=3, to_state=0, node_label=definition.node_label))
    elif definition.action == 'reset_all':
        return # Not active, too dangerous
        await database.execute(delete_results_query.bindparams(node_label=definition.node_label))
        return await database.execute(reset_query.bindparams(node_label=definition.node_label))

@router.get('/queue/detail/{node_label}', tags=['queue'])
async def read_queue_detail(node_label: str):

    # file stats
    file_stats_query = text(f'''
    select mode() within group (order by duration) as common_duration,
    min(time) as min_time, max(time) as max_time
    from {crd.db.schema}.birdnet_input
    where node_label = :node_label and duration >= 3 and sample_rate = 48000
    ''')

    # task stats
    task_stats_query = text(f'''
    select avg(end_on - pickup_on) as avg_runtime, min(end_on - pickup_on) as min_runtime, max(end_on - pickup_on) as max_runtime,
    min(scheduled_on) as min_scheduled_on, max(scheduled_on) as max_scheduled_on, min(end_on) as min_end_on, max(end_on) as max_end_on, sum(end_on - pickup_on) as total_runtime
    from {crd.db.schema}.birdnet_tasks t
    left outer join {crd.db.schema}.birdnet_input i on i.file_id = t.file_id
    where state = 2 and node_label = :node_label and duration >= 3 and sample_rate = 48000
    ''')

    # result stats
    result_stats_query = text(f'''
    select count(result_id), count(distinct case when confidence > 0.9 then result_id end) as count_conf_09
    from {crd.db.schema}.birdnet_results
    left join {crd.db.schema}.birdnet_input on birdnet_input.file_id = birdnet_results.file_id
    where node_label = :node_label and duration >= 3 and sample_rate = 48000
    ''')

    file_stats = await database.fetch_one(file_stats_query.bindparams(node_label = node_label))
    task_stats = await database.fetch_one(task_stats_query.bindparams(node_label = node_label))
    result_stats = await database.fetch_one(result_stats_query.bindparams(node_label = node_label))

    return { 'node_label': node_label, 'file_stats': file_stats, 'task_stats': task_stats, 'result_stats': result_stats }
