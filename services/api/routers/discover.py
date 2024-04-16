from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Query
from sqlalchemy.sql import desc
from sqlalchemy.sql import select, text, func, between

from api.database import database
from api.models import (
    HotspotDataPollinatorsResponse, BirdSpeciesCount
)
from api.tables import (files_image, mm_tags_deployments, pollinators, image_results, files_audio, birdnet_results)

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


@router.get('/discover/birds/top3/{deployment_id}', response_model=List[BirdSpeciesCount])
async def get_top3(deployment_id: int):
    query = select(birdnet_results.c.species, func.count().label('count')).\
        select_from(files_audio).\
        outerjoin(birdnet_results, files_audio.c.file_id == birdnet_results.c.file_id).\
        where(files_audio.c.deployment_id == deployment_id).\
        where(birdnet_results.c.confidence > 0.9).\
        group_by(birdnet_results.c.species).\
        order_by(desc(func.count())).\
        limit(3)

    return await database.fetch_all(query)
