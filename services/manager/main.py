import sys
import secrets
from typing import List, Optional
import databases

import sqlalchemy
from sqlalchemy.sql import insert, update, select, delete, exists, func, and_, not_, desc, text, distinct, LABEL_STYLE_TABLENAME_PLUS_COL
from sqlalchemy.sql.functions import current_timestamp

from fastapi import FastAPI, Request, status, HTTPException, Depends, Header
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from asyncpg.exceptions import ExclusionViolationError, ForeignKeyViolationError

from tables import nodes, locations, deployments, results, tasks, species, species_day, data_records
from models import Deployment, Result, Species, DeploymentResponse, DeploymentRequest, Node, ValidationResult, NodeValidationRequest

sys.path.append('../../')
import credentials as crd

class RecordsDependencyError(BaseException):
    ...

DATABASE_URL = f'postgresql://{crd.db.user}:{crd.db.password}@{crd.db.host}/{crd.db.database}'
database = databases.Database(DATABASE_URL)
engine = sqlalchemy.create_engine(DATABASE_URL)

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
        'name': 'queue',
        'description': 'Machine-Learning queue monitoring and management',
    },
]

app = FastAPI(
    title='Mitwelten Internal REST API',
    description='This service provides REST endpoints to exchange data from [Mitwelten](https://mitwelten.org)',
    contact={'email': 'mitwelten.technik@fhnw.ch'},
    version='1.0.0',
    openapi_tags=tags_metadata,
    servers=[
        {'url': 'https://data.mitwelten.org/manager/v1', 'description': 'Production environment'},
        {'url': 'http://localhost:8000', 'description': 'Development environment'}
    ],
    root_path='/manager/v1',
    root_path_in_servers=False
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

@app.get('/results/', response_model=List[Result], tags=['inferrence'])
async def read_notes():
    query = results.select().where(results.c.confidence > 0.9)
    return await database.fetch_all(query)

@app.get('/species/', tags=['inferrence'])
async def read_species(start: int = 0, end: int = 0, conf: float = 0.9):
    query = select(results.c.species, func.count(results.c.species).label('count')).\
        where(results.c.confidence >= conf).\
        group_by(results.c.species).\
        order_by(desc('count'))
    return await database.fetch_all(query)

@app.get('/species/{spec}', tags=['inferrence']) # , response_model=List[Species]
async def read_species_detail(spec: str, start: int = 0, end: int = 0, conf: float = 0.9):
    query = select(species.c.species, func.min(species.c.time_start).label('earliest'),
            func.max(species.c.time_start).label('latest'),
            func.count(species.c.time_start).label('count')).\
        where(and_(species.c.species == spec, species.c.confidence >= conf)).\
        group_by(species.c.species)
    return await database.fetch_all(query)

@app.get('/species/{spec}/day/', tags=['inferrence']) # , response_model=List[Species]
async def read_species_day(spec: str, start: int = 0, end: int = 0, conf: float = 0.9):
    query = select(species_day.c.species, species_day.c.date,
            func.count(species_day.c.species).label('count')).\
        where(and_(species_day.c.species == spec, species_day.c.confidence >= conf)).\
        group_by(species_day.c.species, species_day.c.date).\
        order_by(species_day.c.date)
    return await database.fetch_all(query)

@app.get('/queue/progress/', tags=['queue'])
async def read_progress():
    query = select(tasks.c.batch_id, tasks.c.state,
            func.count(tasks.c.task_id).label('count')).\
        group_by(tasks.c.batch_id, tasks.c.state).\
        order_by(tasks.c.batch_id)
    progess = await database.fetch_all(query)
    batch_progress = {}
    for row in progess:
        if row.batch_id not in batch_progress:
            batch_progress[row.batch_id] = {
                'complete': 0,
                'pending': 0
            }
        if row.state == 2:
            batch_progress[row.batch_id]['complete'] = row.count
        else:
            batch_progress[row.batch_id]['pending'] += row.count
    return batch_progress

@app.get('/queue/input/', tags=['queue'])
async def read_input():
    query = f'''
    select node_label, count(node_label) as count, min(time) as date_start, max(time) as date_end, sum(file_size) as size
    from {crd.db.schema}.birdnet_input
    group by node_label
    '''
    result = engine.execute(query).fetchall()
    # for row in result:
    #     print(row)
    return result

@app.get('/nodes', tags=['deployments'])
async def read_nodes():
    return await database.fetch_all(select(nodes).order_by(nodes.c.node_label))

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

@app.get('/deployments', response_model=List[DeploymentResponse], tags=['deployments'])
async def read_deployments(node_id: Optional[int] = None) -> List[DeploymentResponse]:

    query = select(deployments.alias('d').outerjoin(nodes.alias('n')).outerjoin(locations.alias('l'))).\
        set_label_style(LABEL_STYLE_TABLENAME_PLUS_COL)
    if node_id != None:
        query = query.where(text('d.node_id = :node_id').bindparams(node_id=node_id))
    result = await database.fetch_all(query)
    response = []
    for r in result:
        d = { c: r['d_'+c] for c in deployments.columns.keys() }
        d['location'] = { c: r['l_'+c] for c in locations.columns.keys() }
        d['node'] = { c: r['n_'+c] for c in nodes.columns.keys() }
        response.append(d)
    return response

@app.get('/deployment/{id}', response_model=DeploymentResponse, tags=['deployments'])
async def read_deployment(id: int) -> DeploymentResponse:

    query = select(deployments.alias('d').outerjoin(nodes.alias('n')).outerjoin(locations.alias('l'))).\
        where(text('deployment_id = :id').bindparams(id=id)).set_label_style(LABEL_STYLE_TABLENAME_PLUS_COL)

    r = await database.fetch_one(query)
    if r == None:
        raise HTTPException(status_code=404, detail='Deployment not found')

    d = { c: r['d_'+c] for c in deployments.columns.keys() }
    d['location'] = { c: r['l_'+c] for c in locations.columns.keys() }
    d['node'] = { c: r['n_'+c] for c in nodes.columns.keys() }
    return d

@app.delete('/deployment/{id}', response_model=None, dependencies=[Depends(check_authentication)], tags=['deployments'])
async def delete_deployment(id: int) -> None:
    transaction = await database.transaction()
    try:
        # asyncpg doesn't support returning affected rowcount yet (https://github.com/encode/databases/issues/61)
        # checking the constraint manually
        exists_files_audio = (exists().where(data_records.c.node_id == deployments.c.node_id))
        q = select(deployments).where(deployments.c.deployment_id == id, not_(exists_files_audio))
        r = await database.fetch_one(q)
        if r == None:
            raise RecordsDependencyError('There are data records referring to the node in the deployment do be deleted.')
        await database.execute(delete(deployments).where(deployments.c.deployment_id == id, not_(exists_files_audio)))
    except RecordsDependencyError as e:
        await transaction.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        await transaction.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    else:
        await transaction.commit()
        return True

@app.post('/deployments', response_model=None, dependencies=[Depends(check_authentication)], tags=['deployments'])
async def add_deployment(body: Deployment) -> None:
    try:
        await database.fetch_one(deployments.insert().values({
            deployments.c.node_id: body.node_id,
            deployments.c.location_id: body.location_id,
            deployments.c.period: body.period,
        }))
    except ExclusionViolationError as e:
        raise HTTPException(status_code=409, detail=str(e))

@app.put('/deployments', response_model=None, dependencies=[Depends(check_authentication)], tags=['deployments'])
async def upsert_deployment(body: DeploymentRequest) -> None:
    transaction = await database.transaction()
    # TODO: put all except the except block into one function to be used in multiple occasions
    try:
        # check if the location exists
        point = f'point({float(body.location.lat)}, {float(body.location.lon)})'
        thresh_1m = 0.0000115
        location_query = f'''
        select location_id from {crd.db.schema}.locations
        where location <-> {point} < {thresh_1m}
        order by location <-> {point}
        limit 1
        '''
        result = await database.fetch_one(query=location_query)

        location_id = None
        if result == None:
            # insert new location
            loc_insert_query = f'''
            insert into {crd.db.schema}.locations(location, type)
            values (point({body.location.lat},{body.location.lon}), 'user-added')
            returning location_id
            '''
            location_id = await database.execute(loc_insert_query)
        else:
            location_id = result.location_id

        if hasattr(body, 'deployment_id') and body.deployment_id != None:
            # this is an update
            # update the record to see if it conflicts
            await database.execute(deployments.update().\
                where(deployments.c.deployment_id == body.deployment_id).\
                values({
                    deployments.c.node_id: body.node_id,
                    deployments.c.location_id: location_id,
                    deployments.c.period: body.period,
                }
            ))
        else:
            # this is a new record, try to insert
            await database.execute(deployments.insert().\
                values({
                    deployments.c.node_id: body.node_id,
                    deployments.c.location_id: location_id,
                    deployments.c.period: body.period,
                }
            ))
    except ExclusionViolationError as e:
        await transaction.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await transaction.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    else:
        await transaction.commit()

@app.put('/validate/deployment', response_model=ValidationResult, tags=['deployments'])
async def validate_deployment(body: DeploymentRequest) -> None:
    transaction = await database.transaction()
    try:
        # check if the location exists
        point = f'point({float(body.location.lat)}, {float(body.location.lon)})'
        thresh_1m = 0.0000115
        location_query = f'''
        select location_id from {crd.db.schema}.locations
        where location <-> {point} < {thresh_1m}
        order by location <-> {point}
        limit 1
        '''
        result = await database.fetch_one(query=location_query)

        location_id = None
        if result == None:
            # insert new location
            loc_insert_query = f'''
            insert into {crd.db.schema}.locations(location, type)
            values (point({body.location.lat},{body.location.lon}), 'user-added')
            returning location_id
            '''
            location_id = await database.execute(loc_insert_query)
        else:
            location_id = result.location_id

        if hasattr(body, 'deployment_id') and body.deployment_id != None:
            # this is an update
            # update the record to see if it conflicts
            await database.execute(deployments.update().\
                where(deployments.c.deployment_id == body.deployment_id).\
                values({
                    deployments.c.node_id: body.node_id,
                    deployments.c.location_id: location_id,
                    deployments.c.period: body.period,
                }
            ))
        else:
            # this is a new record, try to insert
            await database.execute(deployments.insert().\
                values({
                    deployments.c.node_id: body.node_id,
                    deployments.c.location_id: location_id,
                    deployments.c.period: body.period,
                }
            ))
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

@app.get('/', include_in_schema=False)
async def root():
    return {'message': 'Mitwelten ML Backend: query inference results, queue status, etc.'}
