from datetime import date, datetime, timedelta
from typing import List, Optional
from pandas import to_timedelta


from api.database import database
from api.models import PollinatorTypeEnum, TimeSeriesResult
from fastapi import APIRouter, Query
from sqlalchemy.sql import and_, desc, func, select, text

import credentials as crd


router = APIRouter(tags=['pollinator'])

# ------------------------------------------------------------------------------
# POLLINATOR RESULTS
# ------------------------------------------------------------------------------


@router.get('/pollinators/date' , response_model=TimeSeriesResult)
async def detection_dates_by_id(
    pollinator_class: PollinatorTypeEnum = None,  
    conf: float = 0.9,
    bucket_width:str = "1d",
    time_from: Optional[datetime] = Query(None, alias='from', example='2021-09-01T00:00:00.000Z'),
    time_to: Optional[datetime] = Query(None, alias='to', example='2022-08-31T23:59:59.999Z'),
    ) -> TimeSeriesResult:
    time_from_condition = "AND i.time >= :time_from" if time_from else ""
    time_to_condition = "AND i.time <= :time_to" if time_to else ""
    pollinator_class_condition = "and p.class = :pollinator_class" if pollinator_class else ""
    query = text(
    f"""
    SELECT time_bucket(:bucket_width, i.time) AS bucket,
    count(p.class) as detections
    from {crd.db.schema}.pollinators p
    left join {crd.db.schema}.image_results ir ON p.result_id = ir.result_id
    left join {crd.db.schema}.files_image i ON ir.file_id = i.file_id
    where p.confidence >= :conf
    {pollinator_class_condition}
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
    if pollinator_class:
        query = query.bindparams( pollinator_class=pollinator_class.value)

    results = await database.fetch_all(query)
    response = TimeSeriesResult(bucket=[],detections=[])
    for result in results:
        response.bucket.append(result.bucket)
        response.detections.append(result.detections)
    return response