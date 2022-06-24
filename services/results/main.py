import sys
from typing import List

import databases

import sqlalchemy
from sqlalchemy.sql import select, func, and_, desc

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from asyncpg.exceptions import ExclusionViolationError

from tables import nodes, locations, deployments, results, tasks, species, species_day
from models import Deployment, Result, Species

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

@app.get('/deployments', response_model=List[Deployment])
async def read_nodes():
    return await database.fetch_all(select(deployments).select_from(deployments.outerjoin(nodes).outerjoin(locations)))

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

@app.get('/')
async def root():
    return {'message': 'Mitwelten ML Backend: query inference results, queue status, etc.'}
