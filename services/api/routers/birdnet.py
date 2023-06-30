from datetime import date, datetime, timedelta
from typing import List, Optional

from api.database import database
from api.models import Result, ResultFull, ResultsGrouped, TimeSeriesResult, DetectionLocationResult, Point
from api.tables import results, results_file_taxonomy, species, species_day, taxonomy_data

from fastapi import APIRouter, Query
from sqlalchemy.sql import and_, desc, func, select, text, bindparam
from pandas import to_timedelta

import credentials as crd

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

@router.get('/birds/{identifier}/date' , response_model=TimeSeriesResult)
async def detection_dates_by_id(
    identifier: int,  
    conf: float = 0.9,
    bucket_width:str = "1d",
    time_from: Optional[datetime] = Query(None, alias='from', example='2021-09-01T00:00:00.000Z'),
    time_to: Optional[datetime] = Query(None, alias='to', example='2022-08-31T23:59:59.999Z'),
    deployment_ids:List[int] = Query(default=None),
    distinctspecies: bool = False,
    ) -> TimeSeriesResult:
    time_from_condition = "AND (f.time + interval '1 second' * r.time_start) >= :time_from" if time_from else ""
    time_to_condition = "AND (f.time + interval '1 second' * r.time_start) <= :time_to" if time_to else ""
    distinct_arg = "DISTINCT" if distinctspecies else ""
    deployment_filter = "AND f.deployment_id in :deployment_ids" if deployment_ids else ""
    query = text(
    f"""
    SELECT time_bucket(:bucket_width, (f.time + interval '1 second' * r.time_start)) AS bucket,
    count({distinct_arg} r.species) as detections
    from {crd.db.schema}.birdnet_results r
    left join {crd.db.schema}.files_audio f on f.file_id = r.file_id 
    where r.confidence >= :conf
    and r.species in (
        select s.label_sci from {crd.db.schema}.taxonomy_data s where datum_id in (
            select species_id from {crd.db.schema}.taxonomy_tree 
            where species_id = :identifier
            or genus_id = :identifier
            or family_id = :identifier
            or order_id = :identifier
            or class_id = :identifier
            or phylum_id = :identifier
            or kingdom_id = :identifier
            )
        ) 
    {deployment_filter}
    {time_from_condition}
    {time_to_condition}
    GROUP BY bucket
    ORDER BY bucket
    """
    ).bindparams(bucket_width=to_timedelta(bucket_width).to_pytimedelta(),conf=conf, identifier=identifier)
    if time_from:
        query = query.bindparams(time_from = time_from)
    if time_to:
        query = query.bindparams(time_to = time_to)
    if deployment_ids:
        query = query.bindparams( bindparam('deployment_ids', value=deployment_ids, expanding=True))
    results = await database.fetch_all(query)
    response = TimeSeriesResult(bucket=[],detections=[])
    for result in results:
        response.bucket.append(result.bucket)
        response.detections.append(result.detections)
    return response

@router.get('/birds/{identifier}/location' , response_model=List[DetectionLocationResult])
async def detection_locations_by_id(
    identifier: int,  
    conf: float = 0.9,
    time_from: Optional[datetime] = Query(None, alias='from', example='2021-09-01T00:00:00.000Z'),
    time_to: Optional[datetime] = Query(None, alias='to', example='2022-08-31T23:59:59.999Z'),
    distinctspecies: bool = False,
    deployment_ids:List[int] = Query(default=None),
    ) -> List[DetectionLocationResult]:
    time_from_condition = "AND (f.time + interval '1 second' * r.time_start) >= :time_from" if time_from else ""
    time_to_condition = "AND (f.time + interval '1 second' * r.time_start) <= :time_to" if time_to else ""
    distinct_arg = "DISTINCT" if distinctspecies else ""
    deployment_filter = "AND f.deployment_id in :deployment_ids" if deployment_ids else ""
    query = text(
    f"""
    SELECT 
    d.location,
    d.deployment_id,
    count({distinct_arg} r.species) as detections
    from {crd.db.schema}.birdnet_results r
    left join {crd.db.schema}.files_audio f on f.file_id = r.file_id 
    left join {crd.db.schema}.deployments d on f.deployment_id = d.deployment_id
    where r.confidence >= :conf
    and r.species in (
        select s.label_sci from {crd.db.schema}.taxonomy_data s where datum_id in (
            select species_id from {crd.db.schema}.taxonomy_tree 
            where species_id = :identifier
            or genus_id = :identifier
            or family_id = :identifier
            or order_id = :identifier
            or class_id = :identifier
            or phylum_id = :identifier
            or kingdom_id = :identifier
            )
        ) 
    {deployment_filter}
    {time_from_condition}
    {time_to_condition}
    GROUP BY d.deployment_id
    """
    ).bindparams(conf=conf, identifier=identifier)
    if time_from:
        query = query.bindparams(time_from = time_from)
    if time_to:
        query = query.bindparams(time_to = time_to)
    if deployment_ids:
        query = query.bindparams( bindparam('deployment_ids', value=deployment_ids, expanding=True))
    results = await database.fetch_all(query)
    typed_results = []
    for result in results:
        typed_results.append(
            DetectionLocationResult(
            location=Point(lat=result.location[0], lon=result.location[1]),
            detections=result.detections,
            deployment_id=result.deployment_id
            )
        )
    return typed_results


@router.get('/birds/{identifier}/count')#, response_model=List[DetectionLocationResult])
async def detection_count(
    identifier: int,  
    conf: float = 0.9,
    time_from: Optional[datetime] = Query(None, alias='from', example='2021-09-01T00:00:00.000Z'),
    time_to: Optional[datetime] = Query(None, alias='to', example='2022-08-31T23:59:59.999Z'),
    ):
    time_from_condition = "AND (f.time + interval '1 second' * r.time_start) >= :time_from" if time_from else ""
    time_to_condition = "AND (f.time + interval '1 second' * r.time_start) <= :time_to" if time_to else ""
    query = text(
    f"""
    SELECT 
    count(r.species) as detections
    from {crd.db.schema}.birdnet_results r
    left join {crd.db.schema}.files_audio f on f.file_id = r.file_id 
    left join {crd.db.schema}.deployments d on f.deployment_id = d.deployment_id
    where r.confidence >= :conf
    and r.species in (
        select s.label_sci from {crd.db.schema}.taxonomy_data s where datum_id in (
            select species_id from {crd.db.schema}.taxonomy_tree 
            where species_id = :identifier
            or genus_id = :identifier
            or family_id = :identifier
            or order_id = :identifier
            or class_id = :identifier
            or phylum_id = :identifier
            or kingdom_id = :identifier
            )
        ) 
    {time_from_condition}
    {time_to_condition}
    """
    ).bindparams(conf=conf, identifier=identifier)
    if time_from:
        query = query.bindparams(time_from = time_from)
    if time_to:
        query = query.bindparams(time_to = time_to)

    result = await database.fetch_one(query)
    return result.detections

@router.get('/birds/{identifier}/time_of_day')
async def detection_time_of_day(
    identifier: int,  
    conf: float = 0.9,
    bucket_width_m:int = 30,
    time_from: Optional[datetime] = Query(None, alias='from', example='2021-09-01T00:00:00.000Z'),
    time_to: Optional[datetime] = Query(None, alias='to', example='2022-08-31T23:59:59.999Z'),
):
    time_from_condition = "AND (f.time + interval '1 second' * r.time_start) >= :time_from" if time_from else ""
    time_to_condition = "AND (f.time + interval '1 second' * r.time_start) <= :time_to" if time_to else ""
    query = text(
    f"""
    SELECT
    unnest((hist.minute_buckets[2:])[: array_length(hist.minute_buckets,1)-2]) as detections,
    generate_series(0, 24*60-1, :bucket_width_m) AS minute_of_day
    FROM (
        SELECT 
        histogram(
            EXTRACT (hour from (f.time + interval '1 second' * r.time_start))*60 + EXTRACT (minute from (f.time + interval '1 second' * r.time_start)), 0, 24*60, (24*60)/:bucket_width_m) as minute_buckets
        FROM {crd.db.schema}.birdnet_results r
        LEFT JOIN {crd.db.schema}.files_audio f ON f.file_id = r.file_id 
        WHERE r.confidence >=  :conf
        AND r.species IN (
            SELECT s.label_sci FROM {crd.db.schema}.taxonomy_data s WHERE datum_id IN (
                SELECT species_id FROM {crd.db.schema}.taxonomy_tree 
                WHERE species_id =  :identifier 
                OR genus_id =  :identifier 
                OR family_id =  :identifier 
                OR order_id =  :identifier 
                OR class_id =  :identifier 
                OR phylum_id =  :identifier 
                OR kingdom_id =  :identifier 
            )
        )
    {time_from_condition}
    {time_to_condition}
    ) hist
    """
    ).bindparams(identifier=identifier, bucket_width_m = bucket_width_m, conf = conf)
    if time_from:
        query = query.bindparams(time_from = time_from)
    if time_to:
        query = query.bindparams(time_to = time_to)
    results = await database.fetch_all(query)
    return {
        "minuteOfDay":[r.minute_of_day for r in results],
        "detections":[r.detections for r in results]
        }
    
@router.get('/species/parent_taxon/{identifier}/count')#, response_model=List[DetectionLocationResult])
async def species_count_by_parent_taxon(
    identifier: int,  
    conf: float = 0.9,
    limit: int = 20,
    ):
    query = text(
    f"""
    SELECT 
        s.datum_id,
        s.label_sci,
        s.label_de,
        s.label_en,
        count(r.species) as detections
    FROM {crd.db.schema}.taxonomy_data s
    left join {crd.db.schema}.birdnet_results r on r.species = s.label_sci
    WHERE s.datum_id IN (
        select species_id from {crd.db.schema}.taxonomy_tree
                where species_id = :identifier
                or genus_id = :identifier
                or family_id = :identifier
                or order_id = :identifier
                or class_id = :identifier
                or phylum_id = :identifier
                or kingdom_id =:identifier
        )
    AND r.confidence > :conf
    group by s.datum_id
    order by detections desc
    LIMIT :limit
    """
    ).bindparams(conf=conf, identifier=identifier, limit=limit)

    results = await database.fetch_all(query)
    typed_results = [
        dict(
        datum_id=r.datum_id,
        label_sci=r.label_sci,
        label_de = r.label_de,
        label_en = r.label_en,
        detections =r.detections
        )
        for r in results]
    
    return typed_results

@router.get('/birds/detectionlist')
async def get_detected_species_list(
    conf: float = 0.9,
    time_from: Optional[datetime] = Query(None, alias='from', example='2021-09-01T00:00:00.000Z'),
    time_to: Optional[datetime] = Query(None, alias='to', example='2022-08-31T23:59:59.999Z'),
    deployment_ids:List[int] = Query(default=None),
    limit: int = 1000,
    ):
    time_from_condition = "AND (f.time + interval '1 second' * r.time_start) >= :time_from" if time_from else ""
    time_to_condition = "AND (f.time + interval '1 second' * r.time_start) <= :time_to" if time_to else ""
    deployment_filter = "AND f.deployment_id in :deployment_ids" if deployment_ids else ""
    query = text(f"""
        select
            distinct(r.species),
            count(r.species) as detections,
            t.datum_id, 
            t.label_en,
            t.label_de 
        from {crd.db.schema}.birdnet_results r
        left join {crd.db.schema}.files_audio f on f.file_id = r.file_id
        join {crd.db.schema}.taxonomy_data t on t.label_sci = r.species
        where r.confidence >= :conf
        {deployment_filter}
        {time_from_condition}
        {time_to_condition}
        GROUP by r.species, t.datum_id
        order by detections DESC
        LIMIT :limit
    """
    ).bindparams(conf=conf, limit=limit)
    if time_from:
        query = query.bindparams(time_from = time_from)
    if time_to:
        query = query.bindparams(time_to = time_to)
    if deployment_ids:
        query = query.bindparams( bindparam('deployment_ids', value=deployment_ids, expanding=True))
    results = await database.fetch_all(query)
    typed_results = [dict(
        datum_id=r.datum_id,
        label_sci=r.species,
        label_en=r.label_en,
        label_de=r.label_de,
        count=r.detections
    ) for r in results]
    return typed_results