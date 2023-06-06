from datetime import date, datetime, timedelta
from typing import List, Optional
from pandas import to_timedelta


from api.database import database
from api.models import PollinatorTypeEnum, TimeSeriesResult, Point, DetectionLocationResult
from fastapi import APIRouter, Query
from sqlalchemy.sql import and_, desc, func, select, text, bindparam
from sqlalchemy.types import ARRAY, INTEGER

import credentials as crd


router = APIRouter(tags=['pollinator'])

# ------------------------------------------------------------------------------
# POLLINATOR RESULTS
# ------------------------------------------------------------------------------


@router.get('/pollinators/date' , response_model=TimeSeriesResult)
async def detection_dates_by_class(
    pollinator_class:List[PollinatorTypeEnum] = Query(default=None),
    deployment_ids:List[int] = Query(default=None),
    conf: float = 0.9,
    bucket_width:str = "1d",
    time_from: Optional[datetime] = Query(None, alias='from', example='2021-09-01T00:00:00.000Z'),
    time_to: Optional[datetime] = Query(None, alias='to', example='2022-08-31T23:59:59.999Z'),
    ) -> TimeSeriesResult:
    time_from_condition = "AND i.time >= :time_from" if time_from else ""
    time_to_condition = "AND i.time <= :time_to" if time_to else ""
    pollinator_class_condition = "and p.class in :pollinator_classes" if pollinator_class is not None else ""
    deployment_filter = "and i.deployment_id in :deployment_ids" if deployment_ids else ""
    query = text(
    f"""
    SELECT time_bucket(:bucket_width, i.time) AS bucket,
    count(p.class) as detections
    from {crd.db.schema}.pollinators p
    left join {crd.db.schema}.image_results ir ON p.result_id = ir.result_id
    left join {crd.db.schema}.files_image i ON ir.file_id = i.file_id
    where p.confidence >= :conf
    {pollinator_class_condition}
    {deployment_filter}
    {time_from_condition}
    {time_to_condition}
    GROUP BY bucket
    ORDER BY bucket
    """
    ).bindparams(bucket_width=to_timedelta(bucket_width).to_pytimedelta(),conf=conf)
    if time_from:
        query = query.bindparams(time_from = time_from)
    if time_to:
        query = query.bindparams(time_to = time_to)
    if pollinator_class is not None:
        query = query.bindparams(bindparam('pollinator_classes', value=pollinator_class, expanding=True))
    if deployment_ids:
        query = query.bindparams( bindparam('deployment_ids', value=deployment_ids, expanding=True))

    results = await database.fetch_all(query)
    response = TimeSeriesResult(bucket=[],detections=[])
    for result in results:
        response.bucket.append(result.bucket)
        response.detections.append(result.detections)
    return response

@router.get('/pollinators/time_of_day')
async def detection_time_of_day(
    pollinator_class:List[PollinatorTypeEnum] = Query(default=None),
    deployment_ids:List[int] = Query(default=None),
    conf: float = 0.9,
    bucket_width_m:int = 30,
    time_from: Optional[datetime] = Query(None, alias='from', example='2021-09-01T00:00:00.000Z'),
    time_to: Optional[datetime] = Query(None, alias='to', example='2022-08-31T23:59:59.999Z'),
):
    time_from_condition = "AND i.time >= :time_from" if time_from else ""
    time_to_condition = "AND i.time <= :time_to" if time_to else ""
    pollinator_class_condition = "and p.class in :pollinator_classes" if pollinator_class is not None else ""
    deployment_filter = "and i.deployment_id in :deployment_ids" if deployment_ids else ""
    query = text(
    f"""
    SELECT
    unnest((hist.minute_buckets[2:])[: array_length(hist.minute_buckets,1)-2]) as detections,
    generate_series(0, 24*60-1, :bucket_width_m) AS minute_of_day
    FROM (
        SELECT 
        histogram(
            EXTRACT (hour from i.time)*60 + EXTRACT (minute from i.time), 0, 24*60, (24*60)/:bucket_width_m
        ) as minute_buckets
        from {crd.db.schema}.pollinators p
        left join {crd.db.schema}.image_results ir ON p.result_id = ir.result_id
        left join {crd.db.schema}.files_image i ON ir.file_id = i.file_id
        where p.confidence >= :conf
        {pollinator_class_condition}
        {deployment_filter}
        {time_from_condition}
        {time_to_condition}
    ) hist
    """
    ).bindparams(bucket_width_m = bucket_width_m, conf = conf)
    if time_from:
        query = query.bindparams(time_from = time_from)
    if time_to:
        query = query.bindparams(time_to = time_to)
    if pollinator_class:
        query = query.bindparams(bindparam('pollinator_classes', value=pollinator_class, expanding=True))
    if deployment_ids:
        query = query.bindparams( bindparam('deployment_ids', value=deployment_ids, expanding=True))

    results = await database.fetch_all(query)
    return {
        "minuteOfDay":[r.minute_of_day for r in results],
        "detections":[r.detections for r in results]
        }

@router.get('/pollinators/location', response_model=List[DetectionLocationResult])
async def detection_locations_by_id(
    pollinator_class:List[PollinatorTypeEnum] = Query(default=None),
    deployment_ids:List[int] = Query(default=None),
    conf: float = 0.9,
    time_from: Optional[datetime] = Query(None, alias='from', example='2021-09-01T00:00:00.000Z'),
    time_to: Optional[datetime] = Query(None, alias='to', example='2022-08-31T23:59:59.999Z'),
    ) -> List[DetectionLocationResult]:
    time_from_condition = "AND i.time >= :time_from" if time_from else ""
    time_to_condition = "AND i.time <= :time_to" if time_to else ""
    pollinator_class_condition = "and p.class in :pollinator_classes" if pollinator_class is not None else ""
    deployment_filter = "and i.deployment_id in :deployment_ids" if deployment_ids else ""

    query = text(
    f"""
    SELECT 
    d.location,
    d.deployment_id,
    count(p.class) as detections
    from {crd.db.schema}.pollinators p
    left join {crd.db.schema}.image_results ir ON p.result_id = ir.result_id
    left join {crd.db.schema}.files_image i ON ir.file_id = i.file_id
    left join {crd.db.schema}.deployments d on i.deployment_id = d.deployment_id
    where p.confidence >= :conf
    {pollinator_class_condition}
    {deployment_filter}
    {time_from_condition}
    {time_to_condition}
    GROUP BY d.deployment_id

    """
    ).bindparams(conf=conf)
    if time_from:
        query = query.bindparams(time_from = time_from)
    if time_to:
        query = query.bindparams(time_to = time_to)
    if pollinator_class:
        query = query.bindparams(bindparam('pollinator_classes', value=pollinator_class, expanding=True))
    if deployment_ids:
        query = query.bindparams( bindparam('deployment_ids', value=deployment_ids, expanding=True))

    results = await database.fetch_all(query)
    typed_results = []
    for result in results:
        typed_results.append(DetectionLocationResult(
            location=Point(lat=result.location[0], lon=result.location[1]),
            detections=result.detections,
            deployment_id=result.deployment_id
        ))
    return typed_results

@router.get('/files_image/latest')
async def get_latest_image_entries():
    query = text(f"""
    SELECT
        d.deployment_id,
        i.object_name,
        i.time
    FROM
        {crd.db.schema}.deployments d
        JOIN (
            SELECT
                deployment_id,
                MAX(time) AS max_time
            FROM
                {crd.db.schema}.files_image
            GROUP BY
                deployment_id
        ) AS latest ON d.deployment_id = latest.deployment_id
        JOIN {crd.db.schema}.files_image i ON i.deployment_id = latest.deployment_id
        AND i.time = latest.max_time
    where
        upper(d.period) is NULL
    """)
   
    results = await database.fetch_all(query)
    return [
        {"deployment_id":r.deployment_id, "object_name":r.object_name,"time":r.time}
        for r in results
    ]
    