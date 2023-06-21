from typing import List

from api.database import database
from api.dependencies import check_oid_authentication
from api.tables import files_image, deployments, nodes, walk_text, walk
from api.models import SectionText

from fastapi import APIRouter, Depends
from sqlalchemy.sql import select, text

router = APIRouter(tags=['files', 'images', 'walk'])

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
async def get_imagestack(walk_id: int)-> List[SectionText]:
    texts = select(walk_text).\
        where(walk_text.c.walk_id == walk_id).\
        order_by(walk_text.c.percent_in)
    return await database.fetch_all(texts)


@router.get('/walk/{walk_id}')
async def get_walkpath(walk_id: int):
    path = select(walk).where(walk.c.walk_id == walk_id)
    return await database.fetch_all(path)

@router.get('/walk/')
async def get_walk():
    walks = select(walk.c.walk_id, walk.c.title, walk.c.description, walk.c.created_at, walk.c.updated_at)
    return await database.fetch_all(walks)
