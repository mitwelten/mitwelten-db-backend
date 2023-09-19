from datetime import datetime
from typing import List, Optional

from api.database import database
from api.dependencies import check_oid_authentication, AuthenticationChecker
from api.models import ApiErrorResponse, Tag, TagStats
from api.tables import mm_tags_deployments, mm_tags_notes, tags

from asyncpg import ForeignKeyViolationError, StringDataRightTruncationError, UniqueViolationError
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.sql import between, delete, func, insert, select, update
from sqlalchemy.sql.functions import current_timestamp

router = APIRouter(tags=['tags'])

# ------------------------------------------------------------------------------
# TAGS
# ------------------------------------------------------------------------------

@router.get('/tags', response_model=List[Tag], tags=['deployments'])
async def read_tags(deployment_id: Optional[int] = None) -> List[Tag]:
    query = select(tags)
    if deployment_id != None:
        query = query.outerjoin(mm_tags_deployments).where(mm_tags_deployments.c.deployments_deployment_id == deployment_id)
    return await database.fetch_all(query)

@router.get('/tags_stats', response_model=List[TagStats], tags=['deployments'])
async def read_tags_stats(deployment_id: Optional[int] = None) -> List[TagStats]:
    subquery = select(tags.c.tag_id,
            func.count(mm_tags_deployments.c.tags_tag_id).label('deployments'),
            func.count(mm_tags_notes.c.tags_tag_id).label('notes')).\
        outerjoin(mm_tags_deployments).\
        outerjoin(mm_tags_notes).\
        group_by(tags.c.tag_id).subquery()

    query = select(subquery, tags.c.name, tags.c.created_at, tags.c.updated_at).\
        outerjoin(tags, tags.c.tag_id == subquery.c.tag_id).\
        order_by(tags.c.name)
    return await database.fetch_all(query)

@router.put('/tags', dependencies=[Depends(AuthenticationChecker())], responses={
        400: {'model': ApiErrorResponse},
        401: {'model': ApiErrorResponse},
        404: {'model': ApiErrorResponse},
        409: {'model': ApiErrorResponse}})
async def upsert_tag(body: Tag) -> int:
    try:
        if hasattr(body, 'tag_id') and body.tag_id != None:
            result = await database.execute(update(tags).where(tags.c.tag_id == body.tag_id).\
                values({**body.dict(exclude_none=True), tags.c.updated_at: current_timestamp()}).\
                returning(tags.c.tag_id))
            if result == None:
                raise HTTPException(status_code=404, detail='Tag not found')
            return result
        else:
            return await database.execute(insert(tags).values(body.dict(exclude_none=True)).\
                returning(tags.c.tag_id))
    except UniqueViolationError:
        raise HTTPException(status_code=409, detail='Tag with same name already exists')
    except StringDataRightTruncationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete('/tag/{tag_id}', response_model=None, dependencies=[Depends(AuthenticationChecker())])
async def delete_tag(tag_id: int) -> bool:
    '''
    Deletes a tag
    '''
    try:
        await database.execute(delete(tags).where(tags.c.tag_id == tag_id))
    except ForeignKeyViolationError:
        raise HTTPException(status_code=400, detail='Tag is referred to by one or more note or deployment records')
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    else:
        return True
