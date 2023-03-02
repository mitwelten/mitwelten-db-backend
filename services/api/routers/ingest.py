from api.database import database
from api.models import ImageRequest
from api.tables import files_image

from fastapi import APIRouter, HTTPException
from sqlalchemy.sql import insert, select

router = APIRouter()


# ------------------------------------------------------------------------------
# DATA INPUT (INGEST)
# ------------------------------------------------------------------------------

@router.get('/ingest/image/{sha256}', tags=['ingest'])
async def ingest_image(sha256: str) -> None:
    return await database.fetch_one(select(files_image).where(files_image.c.sha256 == sha256))

# todo: auth!?
@router.post('/ingest/image', tags=['ingest'])
async def ingest_image(body: ImageRequest) -> None:

    transaction = await database.transaction()

    try:
        record = {
            files_image.c.object_name: body.object_name,
            files_image.c.sha256: body.sha256,
            files_image.c.time: body.timestamp, # TODO: rename in uploader code
            files_image.c.deployment_id: body.deployment_id,
            files_image.c.file_size: body.file_size,
            files_image.c.resolution: body.resolution
        }
        insert_query = insert(files_image).values(record)
        await database.execute(insert_query)

    except Exception as e:
        await transaction.rollback()
        print(str(e))
        raise HTTPException(status_code=409, detail=str(e))

    else:
        await transaction.commit()
