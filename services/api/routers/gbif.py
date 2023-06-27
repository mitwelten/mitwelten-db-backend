from api.database import database_cache, database
from fastapi import APIRouter, HTTPException, status, Query
from typing import List, Optional
from api.models import TimeSeriesResult, DetectionsByLocation, Point
from sqlalchemy.sql import select, text, bindparam
from datetime import date, datetime, timedelta
import json
from pandas import to_timedelta
import credentials as crd

router = APIRouter(tags=['gbif'])

# ------------------------------------------------------------------------------
# GBIF Occurrence Cache
# ------------------------------------------------------------------------------

@router.get('/gbif/{identifier}/date' , response_model=TimeSeriesResult)
async def gbif_detection_dates_by_id(
    identifier: int,
    bucket_width:str = "1d",
    time_from: Optional[datetime] = Query(None, alias='from', example='2021-09-01T00:00:00.000Z'),
    time_to: Optional[datetime] = Query(None, alias='to', example='2022-08-31T23:59:59.999Z'),
    ) -> TimeSeriesResult:
    time_from_condition = "AND eventdate >= :time_from" if time_from else ""
    time_to_condition = "AND eventdate <= :time_to" if time_to else ""
    query = text(
    f"""
    SELECT time_bucket(:bucket_width, eventdate) AS bucket,
    count(key) as detections
    from {crd.db_cache.schema}.gbif
    where (
    speciesKey = :identifier 
    or speciesKey = :identifier 
    or genusKey = :identifier 
    or familyKey = :identifier 
    or orderKey = :identifier 
    or classKey = :identifier 
    or phylumKey = :identifier 
    or kingdomKey = :identifier 
    )
    {time_from_condition}
    {time_to_condition}
    GROUP BY bucket
    ORDER BY bucket
    """
    ).bindparams(bucket_width=to_timedelta(bucket_width).to_pytimedelta(), identifier=identifier)
    if time_from:
        query = query.bindparams(time_from = time_from)
    if time_to:
        query = query.bindparams(time_to = time_to)
    results = await database_cache.fetch_all(query)
    response = TimeSeriesResult(bucket=[],detections=[])
    for result in results:
        response.bucket.append(result.bucket)
        response.detections.append(result.detections)
    return response

@router.get('/gbif/{identifier}/location' , response_model=List[DetectionsByLocation])
async def gbif_detection_locations_by_id(
    identifier: int,  
    time_from: Optional[datetime] = Query(None, alias='from', example='2021-09-01T00:00:00.000Z'),
    time_to: Optional[datetime] = Query(None, alias='to', example='2022-08-31T23:59:59.999Z'),
    ) -> List[DetectionsByLocation]:
    time_from_condition = "AND eventdate >= :time_from" if time_from else ""
    time_to_condition = "AND eventdate <= :time_to" if time_to else ""
    query = text(
    f"""
    SELECT 
    decimallatitude as lat,
    decimallongitude as lon,
    count(key) as detections
    from {crd.db_cache.schema}.gbif
    where (
    speciesKey = :identifier 
    or speciesKey = :identifier 
    or genusKey = :identifier 
    or familyKey = :identifier 
    or orderKey = :identifier 
    or classKey = :identifier 
    or phylumKey = :identifier 
    or kingdomKey = :identifier 
    )
    {time_from_condition}
    {time_to_condition}
    GROUP BY decimallatitude, decimallongitude
    """
    ).bindparams(identifier=identifier)
    if time_from:
        query = query.bindparams(time_from = time_from)
    if time_to:
        query = query.bindparams(time_to = time_to)

    results = await database_cache.fetch_all(query)
    typed_results = []
    for result in results:
        typed_results.append(
            DetectionsByLocation(
            location=Point(lat=result.lat, lon=result.lon),
            detections=result.detections,
            )
        )
    return typed_results

@router.get('/gbif/{identifier}/count')
async def gbif_detection_count(
    identifier: int,  
    time_from: Optional[datetime] = Query(None, alias='from', example='2021-09-01T00:00:00.000Z'),
    time_to: Optional[datetime] = Query(None, alias='to', example='2022-08-31T23:59:59.999Z'),
    ):
    time_from_condition = "AND eventdate >= :time_from" if time_from else ""
    time_to_condition = "AND eventdate <= :time_to" if time_to else ""
    query = text(
    f"""
    SELECT 
    count(key) as detections
    from {crd.db_cache.schema}.gbif
    where (
    speciesKey = :identifier 
    or speciesKey = :identifier 
    or genusKey = :identifier 
    or familyKey = :identifier 
    or orderKey = :identifier 
    or classKey = :identifier 
    or phylumKey = :identifier 
    or kingdomKey = :identifier 
    )
    {time_from_condition}
    {time_to_condition}
    """
    ).bindparams(identifier=identifier)
    if time_from:
        query = query.bindparams(time_from = time_from)
    if time_to:
        query = query.bindparams(time_to = time_to)

    result = await database_cache.fetch_one(query)
    return result.detections

@router.get('/gbif/{identifier}/time_of_day')
async def gbif_detection_time_of_day(
    identifier: int,  
    bucket_width_m:int = 30,
    time_from: Optional[datetime] = Query(None, alias='from', example='2021-09-01T00:00:00.000Z'),
    time_to: Optional[datetime] = Query(None, alias='to', example='2022-08-31T23:59:59.999Z'),
):
    time_from_condition = "AND eventdate >= :time_from" if time_from else ""
    time_to_condition = "AND eventdate <= :time_to" if time_to else ""
    query = text(
    f"""
    SELECT
    unnest((hist.minute_buckets[2:])[: array_length(hist.minute_buckets,1)-2]) as detections,
    generate_series(0, 24*60-1, :bucket_width_m) AS minute_of_day
    FROM (
        SELECT 
        histogram(
            EXTRACT (hour from eventdate)*60 + EXTRACT (minute from eventdate), 0, 24*60, (24*60)/:bucket_width_m) as minute_buckets
        FROM {crd.db_cache.schema}.gbif
        WHERE (
        speciesKey = :identifier 
        or speciesKey = :identifier 
        or genusKey = :identifier 
        or familyKey = :identifier 
        or orderKey = :identifier 
        or classKey = :identifier 
        or phylumKey = :identifier 
        or kingdomKey = :identifier 
        )
        AND EXTRACT (hour from eventdate)*3600 + EXTRACT (minute from eventdate)*60+EXTRACT (SECOND from eventdate) >0
        {time_from_condition}
        {time_to_condition}
    ) hist
    """
    ).bindparams(identifier=identifier, bucket_width_m = bucket_width_m)
    if time_from:
        query = query.bindparams(time_from = time_from)
    if time_to:
        query = query.bindparams(time_to = time_to)
    results = await database_cache.fetch_all(query)
    return {
        "minuteOfDay":[r.minute_of_day for r in results],
        "detections":[r.detections for r in results]
        }

@router.get('/gbif/{identifier}/datasets')
async def gbif_occurence_datasets(
    identifier: int,
    time_from: Optional[datetime] = Query(None, alias='from', example='2021-09-01T00:00:00.000Z'),
    time_to: Optional[datetime] = Query(None, alias='to', example='2022-08-31T23:59:59.999Z'),
    ):
    time_from_condition = "AND eventdate >= :time_from" if time_from else ""
    time_to_condition = "AND eventdate <= :time_to" if time_to else ""
    query = text(
    f"""
    SELECT distinct(datasetname) as datasetname,
    datasetkey,
    datasetreference
    from {crd.db_cache.schema}.gbif
    where (
    speciesKey = :identifier 
    or speciesKey = :identifier 
    or genusKey = :identifier 
    or familyKey = :identifier 
    or orderKey = :identifier 
    or classKey = :identifier 
    or phylumKey = :identifier 
    or kingdomKey = :identifier 
    )
    {time_from_condition}
    {time_to_condition}
    """
    ).bindparams(identifier=identifier)
    if time_from:
        query = query.bindparams(time_from = time_from)
    if time_to:
        query = query.bindparams(time_to = time_to)
    results = await database_cache.fetch_all(query)
    return [dict(name=r.datasetname if r.datasetname is not None else r.datasetkey,datasetkey=r.datasetkey,reference=r.datasetreference ) for r in results]


@router.get('/gbif/{identifier}/occurences')
async def gbif_occurences_by_id(
    identifier: int,
    time_from: Optional[datetime] = Query(None, alias='from', example='2021-09-01T00:00:00.000Z'),
    time_to: Optional[datetime] = Query(None, alias='to', example='2022-08-31T23:59:59.999Z'),
    limit:int=100,
    offset:int=0,
    with_media_only:bool = False
    ):
    time_from_condition = "AND eventdate >= :time_from" if time_from else ""
    time_to_condition = "AND eventdate <= :time_to" if time_to else ""
    media_filter = "AND media is not NULL" if with_media_only else ""
    query = text(
    f"""
    SELECT eventdate AS ts,
        key as occurence_key,
        taxonkey as taxon_key,
        media,
        datasetname,
        datasetkey
    from {crd.db_cache.schema}.gbif
    where (
    speciesKey = :identifier 
    or speciesKey = :identifier 
    or genusKey = :identifier 
    or familyKey = :identifier 
    or orderKey = :identifier 
    or classKey = :identifier 
    or phylumKey = :identifier 
    or kingdomKey = :identifier 
    )
    {time_from_condition}
    {time_to_condition}
    {media_filter}
    order by eventdate
    limit :limit
    offset :offset
    """
    ).bindparams(identifier=identifier, limit=limit,offset=offset)
    if time_from:
        query = query.bindparams(time_from = time_from)
    if time_to:
        query = query.bindparams(time_to = time_to)
    results = await database_cache.fetch_all(query)
    taxon_keys = list(set([r.taxon_key for r in results]))
    taxon_query = text(f"""
        SELECT 
        datum_id,
        label_sci,
        label_de,
        label_en
        FROM {crd.db.schema}.taxonomy_data
        WHERE datum_id in :taxon_list
    """).bindparams(bindparam('taxon_list', value=taxon_keys, expanding=True))
    taxon_results = await database.fetch_all(taxon_query)
    taxon_mapping = {r.datum_id:dict(label_sci=r.label_sci,label_de=r.label_de,label_en=r.label_en) for r in taxon_results}
   
    response = [
        dict(
        time=r.ts,
        occurenceKey = r.occurence_key,
        taxonKey=r.taxon_key,
        label_sci=taxon_mapping[r.taxon_key].get("label_sci") if r.taxon_key in taxon_mapping.keys() else None,
        label_de=taxon_mapping[r.taxon_key].get("label_de") if r.taxon_key in taxon_mapping.keys() else None,
        label_en=taxon_mapping[r.taxon_key].get("label_en") if r.taxon_key in taxon_mapping.keys() else None,
        media=json.loads(r.media) if r.media is not None else None,
        datasetName=r.datasetname,
        datasetKey = r.datasetkey)
        for r in results]
    
    return response