from api.database import database
from api.dependencies import check_authentication
from api.models import ImageRequest, PaxMeasurement
from api.tables import files_image, data_pax, deployments, nodes

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.sql import insert, select, and_, text

router = APIRouter(tags=['inferrence', 'ingest'])

# ------------------------------------------------------------------------------
# DATA INPUT (INGEST)
# ------------------------------------------------------------------------------

@router.get('/ingest/image/{sha256}')
async def ingest_image(sha256: str) -> None:
    return await database.fetch_one(select(files_image).where(files_image.c.sha256 == sha256))

@router.post('/ingest/image', dependencies=[Depends(check_authentication)])
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

@router.post('/ingest/pax', dependencies=[Depends(check_authentication)])
async def ingest_pax(body: PaxMeasurement):
    transaction = await database.transaction()

    try:
        if body.nodeLabel is not None:
            node_id_subquery = select(nodes.c.node_id).filter(nodes.c.node_label == body.nodeLabel).scalar_subquery()
        elif body.deviceEui is not None:
            node_id_subquery = select(nodes.c.node_id).filter(nodes.c.serial_number == body.deviceEui).scalar_subquery()
        else:
            raise HTTPException(status_code=409, detail="Invalid Node Identifier")
        deployment_id_subquery = select(deployments.c.deployment_id).filter(
            and_(
                deployments.c.node_id == node_id_subquery,
                text("upper(period) is NULL")
            )
        ).scalar_subquery()
        insert_stmt = insert(data_pax).values(
            time=body.time,
            deployment_id=deployment_id_subquery,
            pax=body.pax,
            voltage=body.voltage
        )
        await database.execute(insert_stmt)

    except Exception as e:
        await transaction.rollback()
        print(str(e))
        raise HTTPException(status_code=409, detail=str(e))

    else:
        await transaction.commit()    

