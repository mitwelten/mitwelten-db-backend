import sys
from typing import List
import databases

import sqlalchemy
from sqlalchemy.sql import select, func, and_, desc, text, LABEL_STYLE_TABLENAME_PLUS_COL

from fastapi import FastAPI, Request, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from asyncpg.exceptions import ExclusionViolationError

from tables import nodes, locations, deployments, results, tasks, species, species_day
from models import Deployment, Result, Species, DeploymentResponse, DeploymentRequest, Node

sys.path.append('../../')
import credentials as crd

DATABASE_URL = f'postgresql://{crd.db.user}:{crd.db.password}@{crd.db.host}/{crd.db.database}'
database = databases.Database(DATABASE_URL)
engine = sqlalchemy.create_engine(DATABASE_URL)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        'http://localhost:4200',
        'http://localhost:8080',
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


@app.get('/results/', response_model=List[Result])
async def read_notes():
    query = results.select().where(results.c.confidence > 0.9)
    return await database.fetch_all(query)

@app.get('/species/')
async def read_species(start: int = 0, end: int = 0, conf: float = 0.9):
    query = select(results.c.species, func.count(results.c.species).label('count')).\
        where(results.c.confidence >= conf).\
        group_by(results.c.species).\
        order_by(desc('count'))
    return await database.fetch_all(query)

@app.get('/species/{spec}') # , response_model=List[Species]
async def read_species_detail(spec: str, start: int = 0, end: int = 0, conf: float = 0.9):
    query = select(species.c.species, func.min(species.c.time_start).label('earliest'),
            func.max(species.c.time_start).label('latest'),
            func.count(species.c.time_start).label('count')).\
        where(and_(species.c.species == spec, species.c.confidence >= conf)).\
        group_by(species.c.species)
    return await database.fetch_all(query)

@app.get('/species/{spec}/day/') # , response_model=List[Species]
async def read_species_day(spec: str, start: int = 0, end: int = 0, conf: float = 0.9):
    query = select(species_day.c.species, species_day.c.date,
            func.count(species_day.c.species).label('count')).\
        where(and_(species_day.c.species == spec, species_day.c.confidence >= conf)).\
        group_by(species_day.c.species, species_day.c.date).\
        order_by(species_day.c.date)
    return await database.fetch_all(query)

@app.get('/queue/progress/')
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

@app.get('/queue/input/')
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

@app.get('/nodes')
async def read_nodes():
    return await database.fetch_all(select(nodes))

@app.get('/node/{id}', response_model=Node)
async def read_node(id: int) -> Node:
    return await database.fetch_one(select(nodes).where(nodes.c.node_id == id))

@app.get('/deployments', response_model=List[DeploymentResponse])
async def read_deployments() -> List[DeploymentResponse]:

    query = select(deployments.alias('d').outerjoin(nodes.alias('n')).outerjoin(locations.alias('l'))).\
        set_label_style(LABEL_STYLE_TABLENAME_PLUS_COL)
    result = await database.fetch_all(query)
    response = []
    for r in result:
        d = { c: r['d_'+c] for c in deployments.columns.keys() }
        d['location'] = { c: r['l_'+c] for c in locations.columns.keys() }
        d['node'] = { c: r['n_'+c] for c in nodes.columns.keys() }
        response.append(d)
    return response

@app.get('/deployment/{id}', response_model=DeploymentResponse)
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

@app.post('/deployments', response_model=None)
async def add_node(body: Deployment) -> None:
    try:
        await database.fetch_one(deployments.insert().values({
            deployments.c.node_id: body.node_id,
            deployments.c.location_id: body.location_id,
            deployments.c.period: body.period,
        }))
    except ExclusionViolationError as e:
        raise HTTPException(status_code=409, detail=str(e))

@app.put('/deployments', response_model=None)
async def update_node(body: DeploymentRequest) -> None:
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
            print('adding location...')
            loc_insert_query = f'''
            insert into {crd.db.schema}.locations(location, type)
            values (point({body.location.lat},{body.location.lon}), 'user-added')
            returning location_id
            '''
            location_id = await database.execute(loc_insert_query)
        else:
            print('using existing location...')
            location_id = result.location_id

        if hasattr(body, 'deployment_id') and body.deployment_id != None:
            # this is an update
            # update the record to see if it conflicts
            print('updating...')
            pprint(dict(body))
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
            print('inserting...')
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
        print('inserted/updated, no overlap')
        await transaction.commit()

@app.put('/validate/deployment')
async def validate_node(body: DeploymentRequest) -> None:
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
        print('validator', e)
        await transaction.rollback()
        return True
    except Exception as e:
        print('validator', e)
        await transaction.rollback()
        return True
    else:
        print('validator: no overlap')
        await transaction.rollback()
        return False

@app.get('/')
async def root():
    return {'message': 'Mitwelten ML Backend: query inference results, queue status, etc.'}
