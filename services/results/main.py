import sys
from typing import List
from datetime import datetime

import databases
import sqlalchemy
from sqlalchemy.sql import select, func, and_, desc
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.append('../../')
import credentials as crd

DATABASE_URL = f'postgresql://{crd.db.user}:{crd.db.password}@{crd.db.host}/{crd.db.database}'

origins = [
    'http://localhost:4200',
    'http://localhost:8080',
]

database = databases.Database(DATABASE_URL)
metadata = sqlalchemy.MetaData(schema=crd.db.schema)

results = sqlalchemy.Table(
    'birdnet_results',
    metadata,
    sqlalchemy.Column('result_id',    sqlalchemy.Integer    , primary_key=True),
    sqlalchemy.Column('file_id',      sqlalchemy.Integer    , nullable=False),
    sqlalchemy.Column('time_start',   sqlalchemy.REAL       , nullable=False),
    sqlalchemy.Column('time_end',     sqlalchemy.REAL       , nullable=False),
    sqlalchemy.Column('confidence',   sqlalchemy.REAL       , nullable=False),
    sqlalchemy.Column('species',      sqlalchemy.String(255), nullable=False)
)

species = sqlalchemy.Table(
    'birdnet_inferred_species',
    metadata,
    sqlalchemy.Column('species',    sqlalchemy.String(255)),
    sqlalchemy.Column('confidence', sqlalchemy.REAL),
    sqlalchemy.Column('time_start', sqlalchemy.TIMESTAMP)
)

species_day = sqlalchemy.Table(
    'birdnet_inferred_species_day',
    metadata,
    sqlalchemy.Column('species',    sqlalchemy.String(255)),
    sqlalchemy.Column('confidence', sqlalchemy.REAL),
    sqlalchemy.Column('date',       sqlalchemy.String)
)

tasks = sqlalchemy.Table(
    'birdnet_tasks',
    metadata,
    sqlalchemy.Column('task_id',        sqlalchemy.Integer    , primary_key=True),
    sqlalchemy.Column('file_id',        sqlalchemy.Integer    , nullable=False),
    sqlalchemy.Column('config_id',      sqlalchemy.Integer    , nullable=False),
    sqlalchemy.Column('state',          sqlalchemy.Integer    , nullable=False),
    sqlalchemy.Column('scheduled_on',   sqlalchemy.TIMESTAMP  , nullable=False),
    sqlalchemy.Column('pickup_on',      sqlalchemy.TIMESTAMP  , nullable=False),
    sqlalchemy.Column('end_on',         sqlalchemy.TIMESTAMP  , nullable=False),
    sqlalchemy.Column('batch_id',       sqlalchemy.Integer,     nullable=False),
    schema=crd.db.schema
)

engine = sqlalchemy.create_engine(
    DATABASE_URL
)
metadata.create_all(engine)

class Result(BaseModel):
    result_id: int
    file_id: int
    time_start: float
    time_end: float
    confidence: float
    species: str

class Species(BaseModel):
    species: str
    confidence: float
    time_start: datetime

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
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

@app.get('/')
async def root():
    return {'message': 'Mitwelten ML Backend: query inference results, queue status, etc.'}
