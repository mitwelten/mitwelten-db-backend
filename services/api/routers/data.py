from datetime import datetime
from typing import Optional

from api.database import database
from api.models import DatumResponse, EnvDatum, PaxDatum, Point, EnvTypeEnum
from api.tables import data_env, data_pax, deployments, nodes
from api.dependencies import aggregation_mapper

from fastapi import APIRouter, HTTPException, Query
from pydantic import conint, constr
from sqlalchemy.sql import between, select,  text
from pandas import to_timedelta
import credentials as crd

router = APIRouter(tags=['data'])

# ------------------------------------------------------------------------------
# DATA
# ------------------------------------------------------------------------------

@router.get('/data/{node_label}', response_model=DatumResponse)
async def list_data(
    node_label: constr(regex=r'\d{4}-\d{4}'),
    time_from: Optional[datetime] = Query(None, alias='from', example='2022-06-22T18:00:00.000Z'),
    time_to: Optional[datetime] = Query(None, alias='to', example='2022-06-22T20:00:00.000Z'),
    limit: Optional[conint(ge=1, le=65536)] = 32768,
) -> DatumResponse:
    '''
    List sensor / capture data in timestamp ascending order
    '''
    typecheck = await database.fetch_one(select(nodes.c.node_id, nodes.c.type).where(nodes.c.node_label == node_label))
    if typecheck == None:
        raise HTTPException(status_code=404, detail='Node not found')

    # select the target table
    target = None
    if typecheck['type'] in ['pax', 'Pax']:
        target = data_pax
        typeclass = PaxDatum
    elif typecheck['type'] in ['env', 'HumiTemp', 'HumiTempMoisture', 'Moisture']:
        target = data_env
        typeclass = EnvDatum
    else:
        raise HTTPException(status_code=400, detail='Invalid node type: {}'.format(typecheck['type']))

    # define the join
    query = select(target, nodes.c.node_label.label('nodeLabel')).\
        select_from(target.outerjoin(deployments).outerjoin(nodes))

    node_selection = nodes.c.node_id == typecheck['node_id']

    # define time range criteria
    if time_from and time_to:
        query = query.where(node_selection, between(target.c.time, time_from, time_to))
    elif time_from:
        query = query.where(node_selection, target.c.time >= time_from)
    elif time_to:
        query = query.where(node_selection, target.c.time < time_to)
    else:
        query = query.where(node_selection)

    result = await database.fetch_all(query=query.order_by(target.c.time))
    typed_result = []
    for datum in result:
        typed_result.append(typeclass(type=typecheck['type'], **datum))
    return typed_result


@router.get('/sensordata/pax/{deployment_id}')
async def get_pax_measurements(
    deployment_id: int,
    time_from: Optional[datetime] = Query(None, alias='from', example='2020-06-22T18:00:00.000Z'),
    time_to: Optional[datetime] = Query(None, alias='to', example='2022-06-22T20:00:00.000Z'),
    bucket_width:str = "1d"):
    time_from_condition = "AND time >= :time_from" if time_from else ""
    time_to_condition = "AND time <= :time_to" if time_to else ""
    query = text(f"""
    SELECT time_bucket(:bucket_width, time) AS bucket,
    AVG(pax) as pax
    from {crd.db.schema}.sensordata_pax
    where deployment_id = :deployment_id
    {time_from_condition}
    {time_to_condition}
    group by bucket
    order by bucket
    """).bindparams(bucket_width=to_timedelta(bucket_width).to_pytimedelta(), deployment_id=deployment_id)
    if time_from:
        query = query.bindparams(time_from = time_from)
    if time_to:
        query = query.bindparams(time_to = time_to)
    results = await database.fetch_all(query=query)
    buckets = [r.bucket for r in results]
    pax = [r.pax for r in results]
    return {"buckets":buckets, "pax":pax}

@router.get('/sensordata/pax/{deployment_id}/time_of_day')
async def get_pax_measurements_time_of_day(
    deployment_id: int,
    time_from: Optional[datetime] = Query(None, alias='from', example='2020-06-22T18:00:00.000Z'),
    time_to: Optional[datetime] = Query(None, alias='to', example='2022-06-22T20:00:00.000Z'),
    bucket_width_m:int = 20):
    time_from_condition = "AND time >= :time_from" if time_from else ""
    time_to_condition = "AND time <= :time_to" if time_to else ""
    query = text(f"""
    SELECT
        FLOOR((EXTRACT(hour FROM time) * 60 + EXTRACT(minute FROM time)) / :bucket_width_m) * :bucket_width_m as minute_of_day,
        AVG(pax) as pax
    FROM {crd.db.schema}.sensordata_pax
    WHERE deployment_id = :deployment_id
    {time_from_condition}
    {time_to_condition}
    GROUP BY minute_of_day
    ORDER BY minute_of_day
    """).bindparams(bucket_width_m=bucket_width_m, deployment_id=deployment_id)
    if time_from:
        query = query.bindparams(time_from = time_from)
    if time_to:
        query = query.bindparams(time_to = time_to)
    results = await database.fetch_all(query=query)
    return {
        "minuteOfDay":[r.minute_of_day for r in results],
        "pax":[r.pax for r in results]
        }

@router.get('/sensordata/pax_locations')
async def get_pax_locations(
    time_from: Optional[datetime] = Query(None, alias='from', example='2020-06-22T18:00:00.000Z'),
    time_to: Optional[datetime] = Query(None, alias='to', example='2022-06-22T20:00:00.000Z'),
    ):
    if time_from is not None and time_to is not None:
        time_condition = "WHERE p.time >= :time_from and p.time <= :time_to"
    elif time_from:
        time_condition = "WHERE p.time >= :time_from"
    elif time_to:
        time_condition = "WHERE p.time <= :time_to"
    else:
        time_condition = ""
    query = text(f"""
        SELECT
            p.deployment_id,
            d.location[0] as lat,
            d.location[1] as lon,
            AVG(p.pax) as pax
        FROM {crd.db.schema}.sensordata_pax p
        left join {crd.db.schema}.deployments d on d.deployment_id = p.deployment_id
        {time_condition}
        group by p.deployment_id, lat, lon
    """)
    if time_from:
        query = query.bindparams(time_from = time_from)
    if time_to:
        query = query.bindparams(time_to = time_to)
    results = await database.fetch_all(query=query)
    typed_results = []
    for result in results:
        typed_results.append(
            dict(
            location=Point(lat=result.lat, lon=result.lon),
            pax=result.pax,
            deployment_id=result.deployment_id
            )
        )
    return typed_results


@router.get('/sensordata/{measurement}/{deployment_id}')
async def get_env_measurements(
    measurement: EnvTypeEnum,
    deployment_id: int,
    aggregation:str = "mean",
    bucket_width:str = "1d",
    time_from: Optional[datetime] = Query(None, alias='from', example='2020-06-22T18:00:00.000Z'),
    time_to: Optional[datetime] = Query(None, alias='to', example='2022-06-22T20:00:00.000Z'),
    ):
    time_from_condition = "AND time >= :time_from" if time_from else ""
    time_to_condition = "AND time <= :time_to" if time_to else ""
    aggregation_str = aggregation_mapper(aggregation=aggregation, column_name=measurement.value)
    if aggregation_str is None:
        raise HTTPException(status_code=400, detail='Invalid aggregation method: {}'.format(aggregation))
    query = text(f"""
    SELECT time_bucket(:bucket_width, time) AS bucket,
    {aggregation_str}
    from {crd.db.schema}.sensordata_env
    where deployment_id = :deployment_id
    {time_from_condition}
    {time_to_condition}
    group by bucket
    order by bucket
    """).bindparams(bucket_width=to_timedelta(bucket_width).to_pytimedelta(), deployment_id=deployment_id)
    if time_from:
        query = query.bindparams(time_from = time_from)
    if time_to:
        query = query.bindparams(time_to = time_to)
    results = await database.fetch_all(query=query)
    buckets = [r.bucket for r in results]
    value = [r.value for r in results]
    return {"time":buckets, "value":value}

@router.get('/sensordata/{measurement}/{deployment_id}/time_of_day')
async def get_env_measurement_time_of_day(
    measurement: EnvTypeEnum,
    deployment_id: int,
    aggregation:str = "mean",
    bucket_width_m:int = 30,
    time_from: Optional[datetime] = Query(None, alias='from', example='2020-06-22T18:00:00.000Z'),
    time_to: Optional[datetime] = Query(None, alias='to', example='2022-06-22T20:00:00.000Z'),
    ):
    time_from_condition = "AND time >= :time_from" if time_from else ""
    time_to_condition = "AND time <= :time_to" if time_to else ""
    aggregation_str = aggregation_mapper(aggregation=aggregation, column_name=measurement.value)
    if aggregation_str is None:
        raise HTTPException(status_code=400, detail='Invalid aggregation method: {}'.format(aggregation))
    query = text(f"""
    SELECT
        FLOOR((EXTRACT(hour FROM time) * 60 + EXTRACT(minute FROM time)) / :bucket_width_m) * :bucket_width_m as minute_of_day,
        {aggregation_str}
    from {crd.db.schema}.sensordata_env
    where deployment_id = :deployment_id
    {time_from_condition}
    {time_to_condition}
    group by minute_of_day
    order by minute_of_day
    """).bindparams(bucket_width_m = bucket_width_m, deployment_id=deployment_id)
    if time_from:
        query = query.bindparams(time_from = time_from)
    if time_to:
        query = query.bindparams(time_to = time_to)
    results = await database.fetch_all(query=query)
    return {
        "minuteOfDay":[r.minute_of_day for r in results],
        "value":[r.value for r in results]
        }
