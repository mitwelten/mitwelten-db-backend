import json
import requests
from typing import List, Optional
from datetime import datetime

from api.database import database
from api.dependencies import AuthenticationChecker
from api.tables import (
    files_image, deployments, nodes, walk_text, walk_hotspot, walk, data_pax,
    tags, mm_tags_deployments, pollinators, image_results, birdnet_results,
    files_audio
)
from api.models import (
    SectionText, Walk, HotspotImageSingle, HotspotImageSequence,
    HotspotInfotext, HotspotAudioText, HotspotData, HotspotDataPaxResponse,
    HotspotDataPollinatorsResponse, HotspotDataBirdsResponse
)

from asyncpg.exceptions import ForeignKeyViolationError
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi_cache.decorator import cache
from sqlalchemy.sql import select, text, update, delete, insert, func, between
from sqlalchemy.sql.functions import current_timestamp

router = APIRouter(tags=['images', 'walk'])

# ------------------------------------------------------------------------------
# DATA WALKING
# ------------------------------------------------------------------------------

@router.get('/walk/imagestack/1')
async def get_imagestack():
    images = select(files_image).\
        outerjoin(deployments).\
        outerjoin(nodes).where(deployments.c.deployment_id == 20).\
        order_by(files_image.c.time).limit(2000);
    return await database.fetch_all(images)

@router.get('/walk/imagestack/2')
async def get_imagestack():
    images = text(f'''
    select t.* from (
        select *, row_number() OVER(ORDER BY time ASC) AS row
        from prod.files_image
        where deployment_id = 67
        limit 1000
    ) t where t.row % 20 = 0;
    ''')
    return await database.fetch_all(images)

@router.get('/walk/text/{walk_id}')
async def get_walk_text(walk_id: int)-> List[SectionText]:
    texts = select(walk_text).\
        where(walk_text.c.walk_id == walk_id).\
        order_by(walk_text.c.percent_in)
    return await database.fetch_all(texts)

@router.get('/walk/hotspots/{walk_id}')
async def get_walk_hotspots(walk_id: int)-> List[HotspotData|HotspotInfotext|HotspotImageSingle|HotspotImageSequence|HotspotAudioText]:
    hotspots = select(walk_hotspot).\
        where(walk_hotspot.c.walk_id == walk_id)
    response = await database.fetch_all(hotspots)
    result = []
    for r in response:
        rd = dict(r)
        rd.update(json.loads(rd.pop('data')))
        result.append(rd)
    return result

@router.get('/walk/community-hotspots')
@cache(expire=3600)
def get_community_hotspots():
    url = 'https://beidebasel.wildenachbarn.ch/api/v1.0/mitwelten'
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

@router.get('/walk/data-hotspots/pax', response_model=HotspotDataPaxResponse)
async def get_pax_hotspots(summary: Optional[int] = Query(1, alias='summary', example=1),
                           tag_ids: Optional[List[int]] = Query([136, 137], alias='tag', example='tag=136&tag=137')):
    interval = ['2023-06-16', '2023-09-01'] if summary == 1 else ['2024-06-16', '2024-09-01']
    options = [
        {'label': 'Sommer 2023', 'value': 1},
        {'label': 'Sommer 2024', 'value': 2}
    ]
    subquery = select(text('date(time at time zone \'UTC\') as dt'), tags.c.name.label('tag'), func.avg(data_pax.c.pax).label('pax_avg')).\
        outerjoin(deployments).outerjoin(mm_tags_deployments).outerjoin(tags).\
        where(tags.c.tag_id.in_(tag_ids)).\
        where(between(data_pax.c.time, datetime.fromisoformat(interval[0]), datetime.fromisoformat(interval[1]))).\
        group_by(tags.c.name, text('date(time at time zone \'UTC\')'))
    result = select(subquery.c.tag,
            func.round(func.avg(subquery.c.pax_avg), 1).label('pax_avg'),
            func.round(func.stddev(subquery.c.pax_avg), 1).label('pax_sdev'),
            func.round(func.min(subquery.c.pax_avg), 1).label('pax_min'),
            func.round(func.max(subquery.c.pax_avg), 1).label('pax_max')).\
        group_by(subquery.c.tag)
    return HotspotDataPaxResponse(
        datapoints = await database.fetch_all(result),
        summaryOptions = options,
        chart = 'bar'
    )

@router.get('/walk/data-hotspots/birds', response_model=HotspotDataBirdsResponse)
async def get_pollinator_hotspots(tag_id: int = Query(163, alias='tag', example='tag=163'),
                           summary: Optional[int] = Query(1, alias='summary', example=1)):

    options = [
        {'label': 'Auenwald', 'value': 163},
        {'label': 'Birsufer', 'value': 162},
        {'label': 'Trockenwiese', 'value': 161}
    ]
    if summary == None or summary == 1:
        summary = 163

    time_from = datetime.fromisoformat('2023-01-01')
    time_to = datetime.fromisoformat('2023-12-31')

    query = select(birdnet_results.c.species.label('class'), func.extract('month', func.date(files_audio.c.time)).label('month'), func.count().label('count')).\
        select_from(files_audio).\
        outerjoin(mm_tags_deployments, mm_tags_deployments.c.deployments_deployment_id == files_audio.c.deployment_id).\
            outerjoin(birdnet_results, birdnet_results.c.file_id == files_audio.c.file_id).\
        where(mm_tags_deployments.c.tags_tag_id == summary).\
        where(between(files_audio.c.time, time_from, time_to)).\
        where(birdnet_results.c.confidence > 0.9).\
        where(birdnet_results.c.species.in_(('Sylvia atricapilla', 'Erithacus rubecula', 'Fringilla coelebs', 'Aegithalos caudatus', 'Turdus merula', 'Phylloscopus collybita', 'Certhia brachydactyla'))).\
        group_by(birdnet_results.c.species, text('month')) #.\
        # having(func.count() > 100) #.\
        # order_by(birdnet_results.c.species, text('month'))
    return HotspotDataBirdsResponse(
        datapoints = await database.fetch_all(query),
        summaryOptions = options,
        chart = 'heatmap'
    )

@router.get('/walk/data-hotspots/pollinators', response_model=HotspotDataPollinatorsResponse)
async def get_pollinator_hotspots(tag_id: int = Query(136, alias='tag', example='tag=136'),
                           summary: Optional[int] = Query(1, alias='summary', example=1)):

    # TODO: decide for summary options: years, or locations?
    # for now, the summary options are the locations
    options = [
        {'label': 'Erlebnisweiher', 'value': 136},
        {'label': 'Velodach', 'value': 133}
    ]
    if summary == None or summary == 1:
        summary = 136

    time_from = datetime.fromisoformat('2022-01-01')
    time_to = datetime.fromisoformat('2022-12-31')

    query = select(pollinators.c['class'], func.extract('month', func.date(files_image.c.time)).label('month'), func.count().label('count')).\
        select_from(files_image).\
        outerjoin(mm_tags_deployments, mm_tags_deployments.c.deployments_deployment_id == files_image.c.deployment_id).\
            outerjoin(image_results).outerjoin(pollinators).\
        where(mm_tags_deployments.c.tags_tag_id == summary).\
        where(between(files_image.c.time, time_from, time_to)).\
        where(pollinators.c.confidence > 0.75).\
        group_by(pollinators.c['class'], text('month')).\
        order_by(pollinators.c['class'], text('month'))
    return HotspotDataPollinatorsResponse(
        datapoints = await database.fetch_all(query),
        summaryOptions = options,
        chart = 'heatmap'
    )

@router.get('/walk/{walk_id}')
async def get_walkpath(walk_id: int):
    path = select(walk).where(walk.c.walk_id == walk_id)
    return await database.fetch_all(path)

@router.get('/walk/')
async def get_walk():
    walks = select(walk.c.walk_id, walk.c.title, walk.c.description, walk.c.created_at, walk.c.updated_at)
    return await database.fetch_all(walks)

@router.put('/walk/', dependencies=[Depends(AuthenticationChecker())])
async def upsert_walk(body: Walk) -> None:
    if hasattr(body, 'walk_id') and body.walk_id != None:
        return await database.execute(update(walk).where(walk.c.walk_id == body.walk_id).\
            values({**body.dict(exclude_none=True, by_alias=True), walk.c.updated_at: current_timestamp()}).\
            returning(walk.c.walk_id))
    else:
        return await database.execute(insert(walk).values(body.dict(exclude_none=True, by_alias=True)).\
            returning(walk.c.walk_id))

@router.delete('/walk/{walk_id}', response_model=None, dependencies=[Depends(AuthenticationChecker())])
async def delete_walk(walk_id: int) -> None:
    try:
        await database.fetch_one(delete(walk).where(walk.c.walk_id == walk_id))
    except ForeignKeyViolationError as e:
        raise HTTPException(status_code=409, detail=str(e))
    else:
        return True
