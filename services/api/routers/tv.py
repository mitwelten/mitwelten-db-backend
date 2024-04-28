from api.database import database
from api.tables import (
    files_image, deployments
)
# from api.models import ( )

from fastapi import APIRouter
from sqlalchemy.sql import select, text

router = APIRouter(tags=['images', 'walk'])

@router.post('/tv/stack-selection/')
async def post_stack_selection(body: dict):
    print(body)
    images = select(files_image).\
        where(files_image.c.deployment_id == 824).\
        order_by(files_image.c.time).limit(1000).offset(0);
        # where(files_image.c.file_size < 1000000).\
    return await database.fetch_all(images)

