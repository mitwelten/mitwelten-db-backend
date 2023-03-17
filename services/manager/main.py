import sys
import secrets
from datetime import timedelta, date
from itertools import filterfalse, groupby
from typing import List, Optional
import databases

import sqlalchemy
from sqlalchemy.sql import (
    insert, update, select, delete, exists, func, and_, or_, not_, desc,
    text, distinct, LABEL_STYLE_TABLENAME_PLUS_COL
)
from sqlalchemy.sql.functions import current_timestamp

from fastapi import (
    FastAPI, Request, status, HTTPException, Depends, Header, Query
)
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from asyncpg.exceptions import ExclusionViolationError, ForeignKeyViolationError
from asyncpg.types import Range

from tables import (
    nodes, deployments, results, tasks, species, species_day, data_records,
    files_image, birdnet_input, tags, mm_tag_deployments, mm_tag_entries,
    results_file_taxonomy, taxonomy_data, taxonomy_tree
)
from models import (
    Deployment, Result, Species, DeploymentResponse, DeploymentRequest, Node,
    ValidationResult, NodeValidationRequest, ImageValidationRequest,
    ImageValidationResponse, ImageRequest, QueueInputDefinition,
    QueueUpdateDefinition, ResultFull, ResultsGrouped, Taxon, Tag, TagStats
)

sys.path.append('../../')
import credentials as crd

def unique_everseen(iterable, key=None):
    '''List unique elements, preserving order. Remember all elements ever seen.'''
    seen = set()
    seen_add = seen.add
    if key is None:
        for element in filterfalse(seen.__contains__, iterable):
            seen_add(element)
            yield element
    else:
        for element in iterable:
            k = key(element)
            if k not in seen:
                seen_add(k)
                yield element

class RecordsDependencyException(BaseException):
    ...

class NodeNotDeployedException(BaseException):
    ...

DATABASE_URL = f'postgresql://{crd.db.user}:{crd.db.password}@{crd.db.host}:{crd.db.port}/{crd.db.database}'
print(DATABASE_URL)
database = databases.Database(DATABASE_URL, min_size=5, max_size=10)

tags_metadata = [
    {
        'name': 'authentication',
        'description': 'Handle authentication',
    },
    {
        'name': 'deployments',
        'description': 'Node deployments management',
    },
    {
        'name': 'inferrence',
        'description': 'Machine-Learning inference results',
    },
    {
        'name': 'taxonomy',
        'description': 'Look-up of taxonomy keywords / relationships',
    },
    {
        'name': 'queue',
        'description': 'Machine-Learning queue monitoring and management',
    },
]

app = FastAPI(
    title='Mitwelten Internal REST API',
    description='This service provides REST endpoints to exchange data from [Mitwelten](https://mitwelten.org)',
    contact={'email': 'mitwelten.technik@fhnw.ch'},
    version='2.0.0',
    openapi_tags=tags_metadata,
    servers=[
        {'url': 'https://data.mitwelten.org/manager/v2', 'description': 'Production environment'},
        {'url': 'http://localhost:8000', 'description': 'Development environment'}
    ],
    root_path='/manager/v2',
    root_path_in_servers=False
)

if crd.DEV == True:
    from fastapi.middleware.cors import CORSMiddleware
    app.root_path = '/'
    app.root_path_in_servers=True
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            'http://localhost',              # dev environment
            'http://localhost:4200',         # angular dev environment
        ],
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
)

security = HTTPBasic()

def check_authentication(credentials: HTTPBasicCredentials = Depends(security), authorization: Optional[str] = Header(None)):
    correct_username = secrets.compare_digest(credentials.username, crd.ba.username)
    correct_password = secrets.compare_digest(credentials.password, crd.ba.password)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Incorrect username or password',
            headers={'WWW-Authenticate': 'Basic'},
        )
    return { 'authenticated': True }

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    exc_str = f'{exc}'.replace('\n', ' ').replace('   ', ' ')
    print(f"{request}: {exc_str}")
    content = {'status_code': 10422, 'message': exc_str, 'data': None}
    return JSONResponse(content=content, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

@app.on_event('startup')
async def startup():
    await database.connect()

@app.on_event('shutdown')
async def shutdown():
    await database.disconnect()

@app.get('/login', tags=['authentication'])
def login(login_state: bool = Depends(check_authentication)):
    return login_state

# ------------------------------------------------------------------------------
# BIRDNET RESULTS
# ------------------------------------------------------------------------------

# todo: give endOfRecords (select +1, see if array is full)
# todo: adjustable confidence
@app.get('/results/', response_model=List[Result], tags=['inferrence'])
async def read_results(offset: int = 0, pagesize: int = Query(1000, gte=0, lte=1000)):
    query = results.select().where(results.c.confidence > 0.9).\
        limit(pagesize).offset(offset)
    return await database.fetch_all(query)

# todo: adjustable confidence
@app.get('/results_full/', response_model=List[ResultFull], tags=['inferrence'])
async def read_results_full(offset: int = 0, pagesize: int = Query(1000, gte=0, lte=1000)):
    query = results_file_taxonomy.select().where(results.c.confidence > 0.9).\
        limit(pagesize).offset(offset)
    return await database.fetch_all(query)

@app.get('/results_full/{on_date}', response_model=List[ResultFull], tags=['inferrence'])
async def read_results_full_on_date(on_date: date, offset: int = 0, pagesize: int = Query(1000, gte=0, lte=1000)):
    query = results_file_taxonomy.select().where(and_(func.date(results_file_taxonomy.c.object_time) == on_date, results_file_taxonomy.c.confidence > 0.9)).\
        limit(pagesize).offset(offset)\
        .order_by(results_file_taxonomy.c.object_time)

    return await database.fetch_all(query)

@app.get('/results_full/single/{filter:path}', response_model=List[ResultsGrouped], tags=['inferrence'])
async def read_results_full(filter: str):
    query = select([results_file_taxonomy.c.species, results_file_taxonomy.c.time_start_relative, results_file_taxonomy.c.duration, results_file_taxonomy.c.image_url])\
            .where(and_(results_file_taxonomy.c.confidence > 0.9, results_file_taxonomy.c.object_name == filter))\
            .group_by(results_file_taxonomy.c.species, results_file_taxonomy.c.time_start_relative, results_file_taxonomy.c.duration, results_file_taxonomy.c.image_url)
    results = await database.fetch_all(query)
    return results

@app.get('/results_full/grouped/{from_date}', response_model=List[str], tags=['inferrence'])
async def read_grouped_full(from_date: date, offset: int = 0, pagesize: int = Query(1000, gte=0, lte=1000)):
    query = select(results_file_taxonomy.c.object_name, func.count(results_file_taxonomy.c.object_name))\
        .filter(and_(results_file_taxonomy.c.confidence > 0.9, results_file_taxonomy.c.object_time >= from_date))\
        .group_by(results_file_taxonomy.c.object_name, results_file_taxonomy.c.object_time)\
        .limit(pagesize).offset(offset)

    results = await database.fetch_all(query)
    return [result.object_name for result in results]

@app.get('/species/', tags=['inferrence'])
async def read_species(start: int = 0, end: int = 0, conf: float = 0.9):
    query = select(results.c.species, func.count(results.c.species).label('count')).\
        where(results.c.confidence >= conf).\
        group_by(results.c.species).\
        subquery(name='species')
    labelled_query = select(query).\
        outerjoin(taxonomy_data, query.c.species == taxonomy_data.c.label_sci).\
        order_by(desc(query.c.count)).\
        with_only_columns(query, taxonomy_data.c.label_de, taxonomy_data.c.label_en, taxonomy_data.c.image_url)
    return await database.fetch_all(labelled_query)

@app.get('/species/{spec}', tags=['inferrence']) # , response_model=List[Species]
async def read_species_detail(spec: str, start: int = 0, end: int = 0, conf: float = 0.9):
    query = select(species.c.species, func.min(species.c.time_start).label('earliest'),
            func.max(species.c.time_start).label('latest'),
            func.count(species.c.time_start).label('count')).\
        where(and_(species.c.species == spec, species.c.confidence >= conf)).\
        group_by(species.c.species).subquery(name='species')
    labelled_query = select(query).\
        outerjoin(taxonomy_data, query.c.species == taxonomy_data.c.label_sci).\
        with_only_columns(query, taxonomy_data.c.label_de, taxonomy_data.c.label_en, taxonomy_data.c.image_url)
    return await database.fetch_all(labelled_query)

@app.get('/species/{spec}/day/', tags=['inferrence']) # , response_model=List[Species]
async def read_species_day(spec: str, start: int = 0, end: int = 0, conf: float = 0.9):
    query = select(species_day.c.species, species_day.c.date,
            func.count(species_day.c.species).label('count')).\
        where(and_(species_day.c.species == spec, species_day.c.confidence >= conf)).\
        group_by(species_day.c.species, species_day.c.date).\
        subquery(name='species')
    labelled_query = select(query).\
        outerjoin(taxonomy_data, query.c.species == taxonomy_data.c.label_sci).\
        order_by(query.c.date).\
        with_only_columns(query, taxonomy_data.c.label_de, taxonomy_data.c.label_en)
    return await database.fetch_all(labelled_query)

# ------------------------------------------------------------------------------
# TAXONOMY LOOKUP
# ------------------------------------------------------------------------------

@app.get('/taxonomy/id/{identifier}', response_model=List[Taxon],
    summary='Taxonomy lookup by numeric identifier (GBIF key)',
    description='Lookup taxonomy of a given numeric __GBIF key__, returning the taxon tree with translated labels',
    tags=['taxonomy'])
async def taxonomy_by_id(identifier: int) -> List[Taxon]:
    keyMap = [ # map db fieldnames to keys in GBIF response
        # for one species there may exist subspecies in GBIF,
        # referred to by a usage key, which is used here as identifier in 'species_id'
        {'db': 'species_id', 'gbif': 'usageKey',   'gbif_label': 'scientificName', 'rank': 'SUBSPECIES'},
        # for one speciesKey there may exist synonyms in GBIF,
        # prefer the name that matched with the lookup (canonicalName)
        {'db': 'species_id', 'gbif': 'speciesKey', 'gbif_label': 'canonicalName',  'rank': 'SPECIES'},
        {'db': 'genus_id',   'gbif': 'genusKey',   'gbif_label': 'genus',          'rank': 'GENUS'},
        {'db': 'family_id',  'gbif': 'familyKey',  'gbif_label': 'family',         'rank': 'FAMILY'},
        {'db': 'class_id',   'gbif': 'classKey',   'gbif_label': 'class',          'rank': 'CLASS'},
        {'db': 'phylum_id',  'gbif': 'phylumKey',  'gbif_label': 'phylum',         'rank': 'PHYLUM'},
        {'db': 'kingdom_id', 'gbif': 'kingdomKey', 'gbif_label': 'kingdom',        'rank': 'KINGDOM'}
    ]
    # lookup tree
    tree_columns = ','.join(taxonomy_tree.c.keys())
    query = select(taxonomy_tree).where(text(f':identifier IN ({tree_columns})').bindparams(identifier=identifier)).limit(1)
    tree = await database.fetch_one(query)
    tree = [tree._mapping[k['db']] for k in keyMap[1:]]
    # filter tree until id matches
    tree_offset = tree.index(identifier)
    # query data for remaining ids
    data_query = select(taxonomy_data).where(taxonomy_data.c.datum_id.in_(tuple(tree[tree_offset:])))
    data = await database.fetch_all(data_query)
    data = {datum['datum_id']: datum for datum in data}
    # return array of tree, with rank info added
    return [{**dict(data[t]), 'rank': keyMap[tree_offset+i+1]['rank']} for i,t in enumerate(tree[tree_offset:])]

@app.get('/taxonomy/sci/{identifier}', response_model=List[Taxon],
    summary='Taxonomy lookup by scientific identifier',
    description='Lookup taxonomy of a given __scientific identifier__, returning the taxon tree with translated labels',
    tags=['taxonomy'])
async def taxonomy_by_sci(identifier: str) -> List[Taxon]:
    query = select(taxonomy_data.c.datum_id).where(taxonomy_data.c.label_sci == identifier)
    result = await database.fetch_one(query)
    return await taxonomy_by_id(result['datum_id'])

# ------------------------------------------------------------------------------
# QUEUE MANAGER
# ------------------------------------------------------------------------------

@app.get('/queue/progress/', tags=['queue'])
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

@app.get('/queue/input/', tags=['queue'])
async def read_input():
    query = f'''
    select node_label, count(node_label) as count, min(time) as date_start, max(time) as date_end, sum(file_size) as size
    from {crd.db.schema}.birdnet_input
    group by node_label
    '''
    return await database.execute(query).fetchall()

@app.post('/queue/input/', tags=['queue'])
async def queue_input(definition: QueueInputDefinition):

    select_query = select(birdnet_input.c.file_id, 1, 0, current_timestamp()).\
        outerjoin(tasks).\
        where(birdnet_input.c.sample_rate == 48000, birdnet_input.c.duration >= 3,
            tasks.c.state == None, birdnet_input.c.node_label == definition.node_label)
    insert_query = insert(tasks).from_select(['file_id', 'config_id', 'state', 'scheduled_on'], select_query)
    # 'on conflict do nothing' not implemented.
    # not required here as the records are selected by the fact that they are absent.

    return await database.execute(insert_query)

@app.patch('/queue/input/', tags=['queue'])
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

@app.get('/queue/detail/{node_label}', tags=['queue'])
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

# ------------------------------------------------------------------------------
# NODES
# ------------------------------------------------------------------------------

@app.get('/nodes', tags=['deployments'])
async def read_nodes():
    deployments_subquery = select(func.count(deployments.c.deployment_id)).\
        where(nodes.c.node_id == deployments.c.node_id).scalar_subquery()
    return await database.fetch_all(select(nodes, deployments_subquery.label('deployment_count')).\
        order_by(nodes.c.node_label))

@app.put('/nodes', dependencies=[Depends(check_authentication)], tags=['deployments'])
async def upsert_node(body: Node) -> None:
    if hasattr(body, 'node_id') and body.node_id != None:
        return await database.execute(update(nodes).where(nodes.c.node_id == body.node_id).\
            values({**body.dict(exclude_none=True), nodes.c.updated_at: current_timestamp()}).\
            returning(nodes.c.node_id))
    else:
        return await database.execute(insert(nodes).values(body.dict(exclude_none=True)).\
            returning(nodes.c.node_id))

@app.get('/node/type_options', tags=['deployments'])
@app.get('/node/type_options/{search_term}', tags=['deployments'])
async def get_node_type(search_term: Optional[str] = None) -> List[str]:
    q = select(distinct(nodes.c.type))
    if search_term != None:
        q = q.where(nodes.c.type.ilike(f'{search_term}%'))
    r = await database.fetch_all(q.order_by(nodes.c.type))
    return [v[nodes.c.type] for v in r if v[nodes.c.type] != None]

@app.get('/node/platform_options', tags=['deployments'])
@app.get('/node/platform_options/{search_term}', tags=['deployments'])
async def get_node_platform(search_term: Optional[str] = None) -> List[str]:
    q = select(distinct(nodes.c.platform))
    if search_term != None:
        q = q.where(nodes.c.platform.ilike(f'{search_term}%'))
    r = await database.fetch_all(q.order_by(nodes.c.platform))
    return [v[nodes.c.platform] for v in r if v[nodes.c.platform] != None]

@app.get('/node/connectivity_options', tags=['deployments'])
@app.get('/node/connectivity_options/{search_term}', tags=['deployments'])
async def get_node_connectivity(search_term: Optional[str] = None) -> List[str]:
    q = select(distinct(nodes.c.connectivity))
    if search_term != None:
        q = q.where(nodes.c.connectivity.ilike(f'{search_term}%'))
    r = await database.fetch_all(q.order_by(nodes.c.connectivity))
    return [v[nodes.c.connectivity] for v in r if v[nodes.c.connectivity] != None]

@app.get('/node/power_options', tags=['deployments'])
@app.get('/node/power_options/{search_term}', tags=['deployments'])
async def get_node_power(search_term: Optional[str] = None) -> List[str]:
    q = select(distinct(nodes.c.power))
    if search_term != None:
        q = q.where(nodes.c.power.ilike(f'{search_term}%'))
    r = await database.fetch_all(q.order_by(nodes.c.power))
    return [v[nodes.c.power] for v in r if v[nodes.c.power] != None]

@app.get('/node', response_model=Node, tags=['deployments'])
async def read_node_by_label(label: str) -> Node:
    return await database.fetch_one(select(nodes).where(nodes.c.node_label == label))

@app.get('/node/{id}', response_model=Node, tags=['deployments'])
async def read_node(id: int) -> Node:
    return await database.fetch_one(select(nodes).where(nodes.c.node_id == id))

@app.delete('/node/{id}', response_model=None, dependencies=[Depends(check_authentication)], tags=['deployments'])
async def delete_node(id: int) -> None:
    try:
        await database.fetch_one(delete(nodes).where(nodes.c.node_id == id))
    except ForeignKeyViolationError as e:
        raise HTTPException(status_code=409, detail=str(e))
    else:
        return True

# ------------------------------------------------------------------------------
# DEPLOYMENTS
# ------------------------------------------------------------------------------

def from_inclusive_range(period: Range) -> Range:
    return Range(period.lower, None if period.upper == None else period.upper - timedelta(days=1))

def to_inclusive_range(period: Range) -> Range:
    return Range(period.lower, None if period.upper == None else period.upper + timedelta(days=1))

@app.get('/deployments', response_model=List[DeploymentResponse], tags=['deployments'])
async def read_deployments(node_id: Optional[int] = None) -> List[DeploymentResponse]:

    query = select(deployments.alias('d').outerjoin(nodes.alias('n')).\
        outerjoin(mm_tag_deployments.alias('mm')).outerjoin(tags.alias('t'))).\
        set_label_style(LABEL_STYLE_TABLENAME_PLUS_COL)
    if node_id != None:
        query = query.where(text('d.node_id = :node_id').bindparams(node_id=node_id))
    result = await database.fetch_all(query)
    response = []
    for key, grp in groupby(result, key=lambda x: x['d_deployment_id']):
        grp = list(grp)
        t_l = unique_everseen(grp, lambda x: x['t_tag_id'])
        r = dict(grp[0])
        d = { c: r['d_'+c] for c in deployments.columns.keys() }
        d['node'] = { c: r['n_'+c] for c in nodes.columns.keys() }
        d['period'] = from_inclusive_range(d['period'])
        d['tags'] = [{'tag_id': t['t_tag_id'], 'name': t['t_name']} for t in t_l if t['t_tag_id'] != None]
        response.append(d)
    return response

@app.get('/deployment/{id}', response_model=DeploymentResponse, tags=['deployments'])
async def read_deployment(id: int) -> DeploymentResponse:

    query = select(deployments.alias('d').outerjoin(nodes.alias('n')).\
        outerjoin(mm_tag_deployments.alias('mm')).outerjoin(tags.alias('t'))).\
        where(text('deployment_id = :id').bindparams(id=id)).set_label_style(LABEL_STYLE_TABLENAME_PLUS_COL)

    r = await database.fetch_all(query)
    if r == None:
        raise HTTPException(status_code=404, detail='Deployment not found')

    t_l = unique_everseen(r, lambda x: x['t_tag_id'])
    d = { c: r[0]['d_'+c] for c in deployments.columns.keys() }
    d['node'] = { c: r[0]['n_'+c] for c in nodes.columns.keys() }
    d['period'] = from_inclusive_range(d['period'])
    d['tags'] = [{'tag_id': t['t_tag_id'], 'name': t['t_name']} for t in t_l if t['t_tag_id'] != None]
    return d

@app.delete('/deployment/{id}', response_model=None, dependencies=[Depends(check_authentication)], tags=['deployments'])
async def delete_deployment(id: int) -> None:
    transaction = await database.transaction()
    try:
        # asyncpg doesn't support returning affected rowcount yet (https://github.com/encode/databases/issues/61)
        # checking the constraint manually
        exists_files_audio = (exists().where(data_records.c.deployment_id == deployments.c.deployment_id))
        q = select(deployments).where(deployments.c.deployment_id == id, not_(exists_files_audio))
        r = await database.fetch_one(q)
        if r == None:
            raise RecordsDependencyException('There are data records referring to the node in the deployment do be deleted.')
        await database.execute(delete(deployments).where(deployments.c.deployment_id == id, not_(exists_files_audio)))
    except RecordsDependencyException as e:
        await transaction.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        await transaction.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    else:
        await transaction.commit()
        return True

@app.post('/deployments', response_model=None, dependencies=[Depends(check_authentication)], tags=['deployments'])
@app.put('/deployments', response_model=None, dependencies=[Depends(check_authentication)], tags=['deployments'])
async def upsert_deployment(body: DeploymentRequest) -> None:
    '''
    Insert or update a deployment
    '''

    try:
        values = {
            deployments.c.node_id: body.node_id,
            deployments.c.location: text('point(:lat,:lon)').\
                bindparams(lat=body.location.lat,lon=body.location.lon),
            deployments.c.period: to_inclusive_range(body.period),
        }
        if hasattr(body, 'description') and body.description != None:
            values[deployments.c.description] = body.description

        transaction = await database.transaction()
        if hasattr(body, 'deployment_id') and body.deployment_id != None:
            # this is an update
            # update the record to see if it conflicts
            await database.execute(deployments.update().\
                where(deployments.c.deployment_id == body.deployment_id).\
                values(values))

            # deal with tags
            if hasattr(body, 'tags') and body.tags != None and isinstance(body.tags, list):
                tu = set(body.tags) # tags, unique
                # select from tags where name in list from request or assoc with deployment_id
                r = await database.fetch_all(select(tags.c.tag_id, tags.c.name, mm_tag_deployments.c.deployments_deployment_id.label('deployment_id')).\
                    outerjoin(mm_tag_deployments, mm_tag_deployments.c.tags_tag_id == tags.c.tag_id).\
                    where(or_(tags.c.name.in_(tu), mm_tag_deployments.c.deployments_deployment_id == body.deployment_id)))

                # split tags in already assoc and unassoc
                pred = lambda x: x['deployment_id'] != body.deployment_id

                at = list(filterfalse(pred, r))                           # Associated Tags: don't do anything with those, used for delete filter
                ut = [t for t in filter(pred, r) if t['tag_id'] not in [a['tag_id'] for a in at]] # Unassociated Tags: assoc these
                nt = [t for t in tu if t not in [rt['name'] for rt in r]] # New Tags: add these and assoc
                dt = [t for t in at if t['name'] not in tu]               # Delete Tags: delete these from nm table

                # deassoc Delete Tags (previously associated)
                if len(dt):
                    await database.execute(mm_tag_deployments.delete().where(and_(
                        mm_tag_deployments.c.tags_tag_id.in_([t['tag_id'] for t in dt]),
                        mm_tag_deployments.c.deployments_deployment_id == body.deployment_id)))

                # insert New Tags
                unt = []
                if len(nt):
                    nti = await database.fetch_all(tags.insert().values([{'name': n} for n in nt]).\
                        returning(tags.c.tag_id, tags.c.name))
                    # combine existing (u) with new (n) tags
                    if len(nti): unt.extend([x['tag_id'] for x in nti])

                # insert join records
                if len(ut): unt.extend(set([x['tag_id'] for x in ut]))
                if len(unt):
                    await database.fetch_all(mm_tag_deployments.insert().values(
                        [{'tags_tag_id': t, 'deployments_deployment_id': body.deployment_id} for t in set(unt)]))
            await transaction.commit()

        else:
            # this is a new record, try to insert
            d = await database.fetch_one(deployments.insert().\
                values(values))

            # deal with tags
            if hasattr(body, 'tags') and body.tags != None and isinstance(body.tags, list):
                tu = set(body.tags) # tags, unique
                # select from tags where name in list from request
                r = await database.fetch_all(select(tags.c.tag_id, tags.c.name).\
                    where(tags.c.name.in_(tu)))
                # find the ones that don't exist
                nt = [t for t in tu if t not in [rt['name'] for rt in r]]
                # insert those and collect the returned ids
                ant = [x['tag_id'] for x in r]
                if len(nt):
                    nti = await database.fetch_all(tags.insert().values([{'name': n} for n in nt]).\
                        returning(tags.c.tag_id, tags.c.name))
                    # combine existing with new ones
                    ant.extend([x['tag_id'] for x in nti])
                # insert join records
                if len(ant):
                    await database.fetch_all(mm_tag_deployments.insert().values(
                        [{'tags_tag_id': t, 'deployments_deployment_id': d['deployment_id']} for t in ant]))
            await transaction.commit()

    except ExclusionViolationError as e:
        await transaction.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await transaction.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# ------------------------------------------------------------------------------
# TAGS
# ------------------------------------------------------------------------------

@app.get('/tags', response_model=List[Tag], tags=['deployments', 'tags'])
async def read_tags(deployment_id: Optional[int] = None) -> List[Tag]:
    query = select(tags)
    if deployment_id != None:
        query = query.outerjoin(mm_tag_deployments).where(mm_tag_deployments.c.deployments_deployment_id == deployment_id)
    return await database.fetch_all(query)

@app.get('/tags_stats', response_model=List[TagStats], tags=['deployments', 'tags'])
async def read_tags_stats(deployment_id: Optional[int] = None) -> List[TagStats]:
    subquery = select(tags.c.tag_id,
            func.count(mm_tag_deployments.c.tags_tag_id).label('deployments'),
            func.count(mm_tag_entries.c.tags_tag_id).label('entries')).\
        outerjoin(mm_tag_deployments).\
        outerjoin(mm_tag_entries).\
        group_by(tags.c.tag_id).subquery()

    query = select(subquery, tags.c.name, tags.c.created_at, tags.c.updated_at).\
        outerjoin(tags, tags.c.tag_id == subquery.c.tag_id).\
        order_by(tags.c.name)
    return await database.fetch_all(query)

@app.put('/tags', dependencies=[Depends(check_authentication)], tags=['tags'])
async def upsert_tag(body: Tag) -> None:
    if hasattr(body, 'tag_id') and body.tag_id != None:
        return await database.execute(update(tags).where(tags.c.tag_id == body.tag_id).\
            values({**body.dict(exclude_none=True), tags.c.updated_at: current_timestamp()}).\
            returning(tags.c.tag_id))
    else:
        return await database.execute(insert(tags).values(body.dict(exclude_none=True)).\
            returning(tags.c.tag_id))

@app.delete('/tag/{tag_id}', response_model=None, dependencies=[Depends(check_authentication)], tags=['tags'])
async def delete_tag(tag_id: int) -> None:
    transaction = await database.transaction()
    try:
        await database.execute(delete(tags).where(tags.c.tag_id == tag_id))
    except Exception as e:
        await transaction.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    else:
        await transaction.commit()
        return True

# ------------------------------------------------------------------------------
# VALIDATORS
# ------------------------------------------------------------------------------

@app.put('/validate/deployment', response_model=ValidationResult, tags=['deployments'])
async def validate_deployment(body: DeploymentRequest) -> None:
    transaction = await database.transaction()
    try:

        values = {
            deployments.c.node_id: body.node_id,
            deployments.c.location: text('point(:lat,:lon)').bindparams(lat=body.location.lat,lon=body.location.lon),
            deployments.c.period: to_inclusive_range(body.period),
        }
        if hasattr(body, 'description') and body.description != None:
            values[deployments.c.description] = body.description

        if hasattr(body, 'deployment_id') and body.deployment_id != None:
            # this is an update
            # update the record to see if it conflicts
            await database.execute(deployments.update().\
                where(deployments.c.deployment_id == body.deployment_id).\
                values(values))
        else:
            # this is a new record, try to insert
            await database.execute(deployments.insert().\
                values(values))
    except ExclusionViolationError as e:
        await transaction.rollback()
        return True
    except Exception as e:
        await transaction.rollback()
        return True
    else:
        await transaction.rollback()
        return False

@app.put('/validate/node', response_model=ValidationResult, tags=['deployments'])
async def validate_node(body: NodeValidationRequest) -> ValidationResult:
    r = None
    if hasattr(body, 'node_id') and body.node_id != None:
        r = await database.fetch_one(select(nodes).\
            where(nodes.c.node_label == body.node_label, nodes.c.node_id != body.node_id))
    else:
        r = await database.fetch_one(select(nodes).where(nodes.c.node_label == body.node_label))
    return True if r == None else False

@app.put('/validate/tag', response_model=ValidationResult, tags=['deployments'])
async def validate_tag(body: Tag) -> ValidationResult:
    r = None
    if hasattr(body, 'tag_id') and body.tag_id != None:
        r = await database.fetch_one(select(tags).\
            where(tags.c.name == body.name, tags.c.tag_id != body.tag_id))
    else:
        r = await database.fetch_one(select(tags).where(tags.c.name == body.name))
    return True if r == None else False


@app.post('/validate/image', response_model=ImageValidationResponse, tags=['ingest'])
async def check_image(body: ImageValidationRequest) -> None:

    duplicate_query = text(f'''
    WITH n AS (
        SELECT :sha256 as sha256,
        :node_label ||'/'||to_char(:timestamp at time zone 'UTC', 'YYYY-mm-DD/HH24/') -- file_path (node_label, timestamp)
        || :node_label ||'_'||to_char(:timestamp at time zone 'UTC', 'YYYY-mm-DD"T"HH24-MI-SS"Z"')||:extension -- file_name (node_label, timestamp, extension)
        as object_name
    )
    SELECT f.sha256 = n.sha256 as hash_match,
        f.object_name = n.object_name as object_name_match,
        n.object_name as object_name
    from {crd.db.schema}.files_image f, n
    where (f.sha256 = n.sha256 or f.object_name = n.object_name)
    ''').bindparams(sha256=body.sha256, node_label=body.node_label, timestamp=body.timestamp, extension='.jpg')

    # print(str(query.compile(compile_kwargs={"literal_binds": True})))
    duplicate_result = await database.fetch_one(duplicate_query)

    object_name = None
    if duplicate_result == None:
        object_name_query = text('''
        SELECT :node_label ||'/'||to_char(:timestamp at time zone 'UTC', 'YYYY-mm-DD/HH24/') -- file_path (node_label, timestamp)
        || :node_label ||'_'||to_char(:timestamp at time zone 'UTC', 'YYYY-mm-DD"T"HH24-MI-SS"Z"')||:extension -- file_name (node_label, timestamp, extension)
        as object_name
        ''').bindparams(node_label=body.node_label, timestamp=body.timestamp, extension='.jpg')
        object_name_result = await database.fetch_one(object_name_query)
        object_name = object_name_result._mapping['object_name']
    else:
        object_name = duplicate_result._mapping['object_name']

    deployment_query = select(deployments.c.deployment_id).join(nodes).\
        where(nodes.c.node_label == body.node_label, text('period @> :timestamp ::timestamptz').bindparams(timestamp=body.timestamp))
    deployment_result = await database.fetch_one(deployment_query)

    if duplicate_result == None:
        if deployment_result:
            return { # no duplicate, deployed: validation passed
                'hash_match': False, 'object_name_match': False, 'object_name': object_name,
                **deployment_result._mapping, 'node_deployed': True }
        else:
            return { # no duplicate, NOT deployed: validation failed
                'hash_match': False, 'object_name_match': False, 'object_name': object_name,
                'deployment_id': None, 'node_deployed': False }
    else:
        if deployment_result:
            return { # DUPLICATE, deployed: validation failed
                **duplicate_result._mapping,
                **deployment_result._mapping, 'node_deployed': True }
        else:
            return { # DUPLICATE, NOT deployed: validation failed
                **duplicate_result._mapping,
                'deployment_id': None, 'node_deployed': False }

# ------------------------------------------------------------------------------
# DATA INPUT (INGEST)
# ------------------------------------------------------------------------------

@app.get('/ingest/image/{sha256}', tags=['ingest'])
async def ingest_image(sha256: str) -> None:
    return await database.fetch_one(select(files_image).where(files_image.c.sha256 == sha256))

# todo: auth!?
@app.post('/ingest/image', tags=['ingest'])
async def ingest_image(body: ImageRequest) -> None:

    transaction = await database.transaction()

    try:
        record = {
            files_image.c.object_name: body.object_name,
            files_image.c.sha256: body.sha256,
            files_image.c.time: body.timestamp, # TODO: rename in uploader code
            files_image.c.deployment_id: body.deployment_id,
            files_image.c.file_size: body.file_size,
            files_image.c.resolution: body.resolution
        }
        insert_query = insert(files_image).values(record)
        await database.execute(insert_query)

    except Exception as e:
        await transaction.rollback()
        print(str(e))
        raise HTTPException(status_code=409, detail=str(e))

    else:
        await transaction.commit()

# ------------------------------------------------------------------------------
# ROOT
# ------------------------------------------------------------------------------

@app.get('/', include_in_schema=False)
async def root():
    return {'message': 'Mitwelten ML Backend: query inference results, queue status, etc.'}
