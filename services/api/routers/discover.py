import credentials as crd
from datetime import datetime
from fastapi import APIRouter, Query
from pandas import to_timedelta
from sqlalchemy.sql import select, text, func, between
from typing import Optional

from api.database import database
from api.models import (
    BirdSpeciesCount,
    HotspotDataPollinatorsResponse,
)
from api.tables import (files_image, mm_tags_deployments, pollinators, image_results)

router = APIRouter(tags=['discover'])


@router.get('/discover/pollinators/heatmap/{deployment_id}', response_model=HotspotDataPollinatorsResponse)
async def get_pollinator_hotspots(
    deployment_id: int,
    conf: float = 0.75,
    time_from: Optional[datetime] = Query(None, alias='from', example='2020-06-22T18:00:00.000Z'),
    time_to: Optional[datetime] = Query(None, alias='to', example='2022-06-22T20:00:00.000Z')
):
    query = select(
        pollinators.c['class'],
        func.extract('month', func.date(files_image.c.time)).label('month'),
        func.count().label('count')
    ). \
        select_from(files_image). \
        outerjoin(mm_tags_deployments, mm_tags_deployments.c.deployments_deployment_id == files_image.c.deployment_id). \
        outerjoin(image_results). \
        outerjoin(pollinators). \
        where(mm_tags_deployments.c.deployments_deployment_id == deployment_id). \
        where(between(files_image.c.time, time_from, time_to)). \
        where(pollinators.c.confidence > conf). \
        group_by(pollinators.c['class'], text('month')). \
        order_by(pollinators.c['class'], text('month'))

    return HotspotDataPollinatorsResponse(
        datapoints=await database.fetch_all(query),
        summaryOptions=[],
        chart='heatmap'
    )


@router.get('/discover/birds/top/{deployment_id}')
async def get_stacked_bar(
    deployment_id: int,
    time_from: Optional[datetime] = Query(None, alias='from', example='2020-06-22T18:00:00.000Z'),
    time_to: Optional[datetime] = Query(None, alias='to', example='2024-04-22T20:00:00.000Z'),
    bucket_width: str = "1d",
    confidence: float = 0.9,
    limit_per_day: int = 3) -> list[BirdSpeciesCount]:

    time_from_condition = "AND time >= :time_from" if time_from else ""
    time_to_condition = "AND time <= :time_to" if time_to else ""

    query = text(f"""
    WITH ranked_results AS (
        SELECT
            br.species,
            time_bucket(:bucket_width, time) AS bucket,
            count(*),
            ROW_NUMBER() OVER (PARTITION BY time_bucket(:bucket_width, time) ORDER BY count(*) DESC)
        FROM
            {crd.db.schema}.files_audio AS audio
            LEFT OUTER JOIN {crd.db.schema}.birdnet_results AS br ON audio.file_id = br.file_id
        WHERE
            audio.deployment_id = :deployment_id AND br.confidence > :confidence
            {time_from_condition}
            {time_to_condition}
        GROUP BY br.species, bucket
    )
    SELECT species, bucket, count
    FROM ranked_results
    WHERE row_number <= :limit_per_day
    ORDER BY bucket, count DESC
    """).bindparams(
            bucket_width = to_timedelta(bucket_width).to_pytimedelta(),
            deployment_id = deployment_id,
            confidence = confidence,
            limit_per_day = limit_per_day)

    if time_from:
        query = query.bindparams(time_from = time_from)
    if time_to:
        query = query.bindparams(time_to = time_to)

    result = await database.fetch_all(query=query)
    return [BirdSpeciesCount(
        species = entry["species"],
        count = entry["count"],
        bucket = entry["bucket"]) for entry in result]
