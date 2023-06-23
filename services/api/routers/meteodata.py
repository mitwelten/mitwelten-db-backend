from datetime import datetime, timedelta
from typing import Optional, List

from api.database import database_cache
from api.tables import meteo_station, meteo_parameter, meteo_meteodata
from api.models import MeteoStation, MeteoParameter, MeteoDataset, MeteoMeasurements, MeteoSummary, MeteoMeasurementTimeOfDay
from api.dependencies import AuthenticationChecker

from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.sql import between, select, and_, text
from pandas import to_timedelta

import credentials as crd

router = APIRouter(tags=["meteodata"])

aggregation_mapping = {
        'mean': 'avg(value) as value',
        'sum': 'sum(value) as value',
        'min': 'min(value) as value',
        'max': 'max(value) as value',
        'median': "percentile_cont(0.5) WITHIN GROUP (ORDER BY value) as value",
        'q1': "percentile_cont(0.25) WITHIN GROUP (ORDER BY value) as value",
        'q3': "percentile_cont(0.75) WITHIN GROUP (ORDER BY value) as value",
    }

# ------------------------------------------------------------------------------
# Meteodata
# ------------------------------------------------------------------------------

@router.get("/meteo/station", response_model=List[MeteoStation])
async def list_stations(station_id: str = None) -> List[MeteoStation]:
    query = meteo_station.select()
    if station_id:
        query = query.where(meteo_station.c.station_id == station_id)
    results = await database_cache.fetch_all(query=query)
    if results == None:
        raise HTTPException(status_code=400, detail="nothing found")
    typed_result = []
    for datum in results:
        typed_result.append(MeteoStation(**datum))
    return typed_result

@router.get("/meteo/parameter", response_model=List[MeteoParameter])
async def list_parameters(param_id: str = None) -> List[MeteoParameter]:
    query = meteo_parameter.select()
    if param_id:
        query = query.where(meteo_parameter.c.param_id == param_id)
    results = await database_cache.fetch_all(query=query)
    if results == None:
        raise HTTPException(status_code=400, detail="nothing found")
    typed_result = []
    for datum in results:
        typed_result.append(MeteoParameter(**datum))
    return typed_result

@router.get("/meteo/dataset", response_model=List[MeteoDataset])
async def list_datasets(
    station_id: str = None, unit: str = None
) -> List[MeteoDataset]:
    args = {}
    if station_id:
        station_filter = "WHERE station_id = :station_id"
        args['station_id'] = station_id
    else:
        station_filter = ""
    if unit:

        unit_filter = "WHERE  p.unit = :unit" if unit else ""
        args['unit'] = unit
    else:
        unit_filter = ""

    query = text(
        f"""
    SELECT p.param_id, p.unit, p.description, s.station_id, s.station_name, s.data_src, md.last_measurement
    FROM {crd.db_cache.schema}.parameter p
    JOIN (
    SELECT 
        DISTINCT ON (param_id, station_id)
        max(ts) as last_measurement,
        param_id,
        station_id
    FROM {crd.db_cache.schema}.meteodata
    {station_filter}
    group by station_id, param_id
    ) md ON md.param_id = p.param_id
    JOIN {crd.db_cache.schema}.station s ON s.station_id = md.station_id
    {unit_filter}
    order by p.description
    """
    )

    results = await database_cache.fetch_all(str(query), args)
    typed_result = []
    for result in results:
        typed_result.append(MeteoDataset(**result))
    return typed_result

@router.get("/meteo/measurements/{station_id}/{param_id}", response_model=MeteoMeasurements)
async def get_measurements(
    station_id: str,
    param_id: str,
    bucket_width:str = "1d",
    aggregation:str = "mean",
    time_from: Optional[datetime] = Query(None, alias='from', example='2021-09-01T00:00:00.000Z'),
    time_to: Optional[datetime] = Query(None, alias='to', example='2022-08-31T23:59:59.999Z'),
    is_allowed: bool = Depends(AuthenticationChecker())
) -> MeteoMeasurements:
    aggregation_str = aggregation_mapping.get(aggregation)
    if aggregation_str is None:
        raise HTTPException(status_code=422, detail=f'Invalid aggregation method: {aggregation}')
    
    time_from_condition = "AND ts >= :time_from" if time_from else ""
    time_to_condition = "AND ts <= :time_to" if time_to else ""
    query = text(
    f"""
    SELECT time_bucket(:bucket_width, ts) AS time,
    {aggregation_str}
    FROM {crd.db_cache.schema}.meteodata
    WHERE param_id = :param_id and station_id = :station_id
    {time_from_condition}
    {time_to_condition}
    GROUP BY time
    ORDER BY time
    """
    ).bindparams(bucket_width=to_timedelta(bucket_width).to_pytimedelta(),param_id=param_id, station_id=station_id)
    if time_from:
        query = query.bindparams(time_from = time_from)
    if time_to:
        query = query.bindparams(time_to = time_to)

    results = await database_cache.fetch_all(query)

    response = MeteoMeasurements(time=[],value=[])
    for result in results:
        response.time.append(result.time)
        response.value.append(result.value)
    return response


@router.get("/meteo/measurements_time_of_day/{station_id}/{param_id}", response_model=MeteoMeasurementTimeOfDay)
async def get_measurements_tod(
    station_id: str,
    param_id: str,
    bucket_width_m:int = 30,
    aggregation:str = "mean",
    time_from: Optional[datetime] = Query(None, alias='from', example='2021-09-01T00:00:00.000Z'),
    time_to: Optional[datetime] = Query(None, alias='to', example='2022-08-31T23:59:59.999Z'),
    is_allowed: bool = Depends(AuthenticationChecker())
)-> MeteoMeasurementTimeOfDay:
    aggregation_str = aggregation_mapping.get(aggregation)
    if aggregation_str is None:
        raise HTTPException(status_code=422, detail=f'Invalid aggregation method: {aggregation}')
    
    time_from_condition = "AND ts >= :time_from" if time_from else ""
    time_to_condition = "AND ts <= :time_to" if time_to else ""
    query = text(
    f"""
    SELECT
    FLOOR((EXTRACT(hour FROM ts) * 60 + EXTRACT(minute FROM ts)) / :bucket_width_m) * :bucket_width_m as minute_of_day,
    {aggregation_str}
    FROM {crd.db_cache.schema}.meteodata
    WHERE param_id = :param_id and station_id = :station_id
    {time_from_condition}
    {time_to_condition}
    GROUP BY minute_of_day
    ORDER BY minute_of_day
    """
    ).bindparams(bucket_width_m=bucket_width_m,param_id=param_id, station_id=station_id)
    if time_from:
        query = query.bindparams(time_from = time_from)
    if time_to:
        query = query.bindparams(time_to = time_to)

    results = await database_cache.fetch_all(query)
    response = MeteoMeasurementTimeOfDay(minute_of_day=[],value=[])
    for result in results:
        response.minute_of_day.append(result.minute_of_day)
        response.value.append(result.value)
    return response



@router.get("/meteo/summary/{station_id}/{param_id}", response_model=MeteoSummary)
async def get_summary(
    station_id: str,
    param_id: str,
    time_from: Optional[datetime] = Query(None, alias='from', example='2021-09-01T00:00:00.000Z'),
    time_to: Optional[datetime] = Query(None, alias='to', example='2022-08-31T23:59:59.999Z'),
    is_allowed: bool = Depends(AuthenticationChecker())
) -> MeteoSummary:
    time_from_condition = "AND ts >= :time_from" if time_from else ""
    time_to_condition = "AND ts <= :time_to" if time_to else ""
    query = text(
    f"""
    SELECT 
    max(value) as maximum,
    min(value) as minimum,
    avg(value) as mean,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY value) as median,
    percentile_cont(0.25) WITHIN GROUP (ORDER BY value) as q1,
    percentile_cont(0.75) WITHIN GROUP (ORDER BY value) as q3,
    MAX(value) - MIN(value) AS range,
    VARIANCE(value) AS variance,
    STDDEV(value) as stddev,
    min(ts) as min_time,
    max(ts) as max_time,
    count(value) as count
    FROM {crd.db_cache.schema}.meteodata
    WHERE param_id = :param_id and station_id = :station_id
    {time_from_condition}
    {time_to_condition}
    """
    ).bindparams(param_id=param_id, station_id=station_id)
    if time_from:
        query = query.bindparams(time_from = time_from)
    if time_to:
        query = query.bindparams(time_to = time_to)

    result = await database_cache.fetch_one(query)
    return MeteoSummary(**result)