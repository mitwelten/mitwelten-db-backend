from datetime import date
from typing import List

from api.database import database
from api.models import Result, ResultFull, ResultsGrouped
from api.tables import results, results_file_taxonomy, species, species_day, taxonomy_data

from fastapi import APIRouter, Query
from sqlalchemy.sql import and_, desc, func, select

router = APIRouter(tags=['inferrence'])

# ------------------------------------------------------------------------------
# BIRDNET RESULTS
# ------------------------------------------------------------------------------

# todo: give endOfRecords (select +1, see if array is full)
# todo: adjustable confidence
@router.get('/results/', response_model=List[Result])
async def read_results(offset: int = 0, pagesize: int = Query(1000, gte=0, lte=1000)):
    query = results.select().where(results.c.confidence > 0.9).\
        limit(pagesize).offset(offset)
    return await database.fetch_all(query)

# todo: adjustable confidence
@router.get('/results_full/', response_model=List[ResultFull])
async def read_results_full(offset: int = 0, pagesize: int = Query(1000, gte=0, lte=1000)):
    query = results_file_taxonomy.select().where(results.c.confidence > 0.9).\
        limit(pagesize).offset(offset)
    return await database.fetch_all(query)

@router.get('/results_full/{on_date}', response_model=List[ResultFull])
async def read_results_full_on_date(on_date: date, offset: int = 0, pagesize: int = Query(1000, gte=0, lte=1000)):
    query = results_file_taxonomy.select().where(and_(func.date(results_file_taxonomy.c.object_time) == on_date, results_file_taxonomy.c.confidence > 0.9)).\
        limit(pagesize).offset(offset)\
        .order_by(results_file_taxonomy.c.object_time)

    return await database.fetch_all(query)

@router.get('/results_full/single/{filter:path}', response_model=List[ResultsGrouped])
async def read_results_full(filter: str):
    query = select([results_file_taxonomy.c.species, results_file_taxonomy.c.time_start_relative, results_file_taxonomy.c.duration, results_file_taxonomy.c.image_url])\
            .where(and_(results_file_taxonomy.c.confidence > 0.9, results_file_taxonomy.c.object_name == filter))\
            .group_by(results_file_taxonomy.c.species, results_file_taxonomy.c.time_start_relative, results_file_taxonomy.c.duration, results_file_taxonomy.c.image_url)
    results = await database.fetch_all(query)
    return results

@router.get('/results_full/grouped/{from_date}', response_model=List[str])
async def read_grouped_full(from_date: date, offset: int = 0, pagesize: int = Query(1000, gte=0, lte=1000)):
    query = select(results_file_taxonomy.c.object_name, func.count(results_file_taxonomy.c.object_name))\
        .filter(and_(results_file_taxonomy.c.confidence > 0.9, results_file_taxonomy.c.object_time >= from_date))\
        .group_by(results_file_taxonomy.c.object_name, results_file_taxonomy.c.object_time)\
        .limit(pagesize).offset(offset)

    results = await database.fetch_all(query)
    return [result.object_name for result in results]

@router.get('/species/')
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

@router.get('/species/{spec}') # , response_model=List[Species]
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

@router.get('/species/{spec}/day/') # , response_model=List[Species]
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
