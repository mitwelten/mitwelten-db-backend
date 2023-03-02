from typing import List, Optional

from api.database import database
from api.dependencies import check_authentication
from api.models import Tag, TagStats
from api.tables import mm_tag_deployments, mm_tag_entries, tags

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.sql import delete, select, func, update, insert
from sqlalchemy.sql.functions import current_timestamp

router = APIRouter()


# ------------------------------------------------------------------------------
# TAGS
# ------------------------------------------------------------------------------

@router.get('/tags', response_model=List[Tag], tags=['deployments', 'tags'])
async def read_tags(deployment_id: Optional[int] = None) -> List[Tag]:
    query = select(tags)
    if deployment_id != None:
        query = query.outerjoin(mm_tag_deployments).where(mm_tag_deployments.c.deployments_deployment_id == deployment_id)
    return await database.fetch_all(query)

@router.get('/tags_stats', response_model=List[TagStats], tags=['deployments', 'tags'])
async def read_tags_stats(deployment_id: Optional[int] = None) -> List[TagStats]:
    subquery = select(tags.c.tag_id,
            func.count(mm_tag_deployments.c.tags_tag_id).label('deployments'),
            func.count(mm_tag_entries.c.tags_tag_id).label('entries')).\
        outerjoin(mm_tag_deployments).\
        outerjoin(mm_tag_entries).\
        group_by(tags.c.tag_id).subquery()

    query = select(subquery, tags.c.name, tags.c.created_at, tags.c.updated_at).\
        outerjoin(tags, tags.c.tag_id == subquery.c.tag_id).\
        order_by(tags.c.name)
    return await database.fetch_all(query)

@router.put('/tags', dependencies=[Depends(check_authentication)], tags=['tags'])
async def upsert_tag(body: Tag) -> None:
    if hasattr(body, 'tag_id') and body.tag_id != None:
        return await database.execute(update(tags).where(tags.c.tag_id == body.tag_id).\
            values({**body.dict(exclude_none=True), tags.c.updated_at: current_timestamp()}).\
            returning(tags.c.tag_id))
    else:
        return await database.execute(insert(tags).values(body.dict(exclude_none=True)).\
            returning(tags.c.tag_id))

@router.delete('/tag/{tag_id}', response_model=None, dependencies=[Depends(check_authentication)], tags=['tags'])
async def delete_tag(tag_id: int) -> None:
    transaction = await database.transaction()
    try:
        await database.execute(delete(tags).where(tags.c.tag_id == tag_id))
    except Exception as e:
        await transaction.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    else:
        await transaction.commit()
        return True
