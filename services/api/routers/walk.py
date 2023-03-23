
from api.database import database
from api.dependencies import check_oid_authentication
from api.tables import files_image, deployments, nodes

from fastapi import APIRouter, Depends
from sqlalchemy.sql import select

router = APIRouter(tags=['files', 'images'])

# ------------------------------------------------------------------------------
# DATA WALKING
# ------------------------------------------------------------------------------

@router.get('/walk/imagestack', dependencies=[Depends(check_oid_authentication)])
async def get_imagestack():
    images = select(files_image).\
        outerjoin(deployments).\
        outerjoin(nodes).where(deployments.c.deployment_id == 20).\
        order_by(files_image.c.time).limit(2000);
    return await database.fetch_all(images)
