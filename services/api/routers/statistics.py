from datetime import datetime
from typing import Optional

from api.database import database
from fastapi import APIRouter, Depends, Request, HTTPException, status, Query
from api.dependencies import AuthenticationChecker
from sqlalchemy.sql import select, text, bindparam
from typing import List
from api.models import EnvironmentEntry, Point
import credentials as crd

router = APIRouter(tags=['statistics'])

# ------------------------------------------------------------------------------
# Measurement statistics for image and audio files
# ------------------------------------------------------------------------------

@router.get('/statistics/audio/total_duration')
async def get_total_recording_duration(
    time_from: Optional[datetime] = Query(None, alias='from', example='2021-09-01T00:00:00.000Z'),
    time_to: Optional[datetime] = Query(None, alias='to', example='2022-08-31T23:59:59.999Z'),
    deployment_ids:List[int] = Query(default=None),
    ):
    if deployment_ids is None:
        return 0
    time_from_condition = "AND time >= :time_from" if time_from else ""
    time_to_condition = "AND time <= :time_to" if time_to else ""
    query = text(
    f"""
    SELECT SUM(duration) as total_duration
    FROM {crd.db.schema}.files_audio
    WHERE deployment_id in :deployment_ids
    {time_from_condition}
    {time_to_condition}
    """
    ).bindparams( bindparam('deployment_ids', value=deployment_ids, expanding=True))
    if time_from:
        query = query.bindparams(time_from = time_from)
    if time_to:
        query = query.bindparams(time_to = time_to)
    result = await database.fetch_one(query)
    return int(result.total_duration)


@router.get('/statistics/audio/daily_recordings')
async def get_recording_duration_per_day(
    time_from: Optional[datetime] = Query(None, alias='from', example='2021-09-01T00:00:00.000Z'),
    time_to: Optional[datetime] = Query(None, alias='to', example='2022-08-31T23:59:59.999Z'),
    deployment_ids:List[int] = Query(default=None),
    ):
    if deployment_ids is None:
        return None
    time_from_condition = "AND time >= :time_from" if time_from else ""
    time_to_condition = "AND time <= :time_to" if time_to else ""
    query = text(
    f"""
    SELECT
    time_bucket('1d', time) AS bucket,
    CAST(sum(duration) AS INTEGER) as recording_seconds
    FROM {crd.db.schema}.files_audio
    WHERE deployment_id in :deployment_ids
    {time_from_condition}
    {time_to_condition}
    GROUP BY bucket
    """
    ).bindparams( bindparam('deployment_ids', value=deployment_ids, expanding=True))
    if time_from:
        query = query.bindparams(time_from = time_from)
    if time_to:
        query = query.bindparams(time_to = time_to)
    result = await database.fetch_all(query)
    return result
    
    
@router.get('/statistics/image/count')
async def get_total_image_count(
    time_from: Optional[datetime] = Query(None, alias='from', example='2021-09-01T00:00:00.000Z'),
    time_to: Optional[datetime] = Query(None, alias='to', example='2022-08-31T23:59:59.999Z'),
    deployment_ids:List[int] = Query(default=None),
    ):
    if deployment_ids is None:
        return 0
    time_from_condition = "AND time >= :time_from" if time_from else ""
    time_to_condition = "AND time <= :time_to" if time_to else ""
    query = text(
    f"""
    SELECT COUNT(*) as image_count
    FROM {crd.db.schema}.files_image
    WHERE deployment_id in :deployment_ids
    {time_from_condition}
    {time_to_condition}
    """
    ).bindparams( bindparam('deployment_ids', value=deployment_ids, expanding=True))
    if time_from:
        query = query.bindparams(time_from = time_from)
    if time_to:
        query = query.bindparams(time_to = time_to)
    result = await database.fetch_one(query)
    return int(result.image_count)

@router.get('/statistics/image/daily_image_count')
async def get_image_count_per_day(
    time_from: Optional[datetime] = Query(None, alias='from', example='2021-09-01T00:00:00.000Z'),
    time_to: Optional[datetime] = Query(None, alias='to', example='2022-08-31T23:59:59.999Z'),
    deployment_ids:List[int] = Query(default=None),
    ):
    if deployment_ids is None:
        return None
    time_from_condition = "AND time >= :time_from" if time_from else ""
    time_to_condition = "AND time <= :time_to" if time_to else ""
    query = text(
    f"""
    SELECT
    time_bucket('1d', time) AS bucket,
    count(*) as image_count
    FROM {crd.db.schema}.files_image
    WHERE deployment_id in :deployment_ids
    {time_from_condition}
    {time_to_condition}
    GROUP BY bucket
    """
    ).bindparams( bindparam('deployment_ids', value=deployment_ids, expanding=True))
    if time_from:
        query = query.bindparams(time_from = time_from)
    if time_to:
        query = query.bindparams(time_to = time_to)
    result = await database.fetch_all(query)
    return result