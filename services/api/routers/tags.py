from datetime import datetime
from typing import List, Optional

from api.database import database
from api.dependencies import check_oid_authentication
from api.models import ApiErrorResponse, Tag, TagStats
from api.tables import mm_tags_deployments, mm_tags_entries, tags

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
            func.count(mm_tags_entries.c.tags_tag_id).label('entries')).\
        outerjoin(mm_tags_deployments).\
        outerjoin(mm_tags_entries).\
        group_by(tags.c.tag_id).subquery()

    query = select(subquery, tags.c.name, tags.c.created_at, tags.c.updated_at).\
        outerjoin(tags, tags.c.tag_id == subquery.c.tag_id).\
        order_by(tags.c.name)
    return await database.fetch_all(query)

@router.put('/tags', dependencies=[Depends(check_oid_authentication)])
async def upsert_tag(body: Tag) -> None:
    if hasattr(body, 'tag_id') and body.tag_id != None:
        return await database.execute(update(tags).where(tags.c.tag_id == body.tag_id).\
            values({**body.dict(exclude_none=True), tags.c.updated_at: current_timestamp()}).\
            returning(tags.c.tag_id))
    else:
        return await database.execute(insert(tags).values(body.dict(exclude_none=True)).\
            returning(tags.c.tag_id))

@router.delete('/tag/{tag_id}', response_model=None, dependencies=[Depends(check_oid_authentication)])
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

@router.put('/viz/tag', response_model=None, dependencies=[Depends(check_oid_authentication)], tags=['viz'], responses={
        400: {"model": ApiErrorResponse},
        404: {"model": ApiErrorResponse},
        409: {"model": ApiErrorResponse}})
async def put_viz_tag(body: Tag) -> None:
    '''
    Add a new tag or update an existing one
    '''

    transaction = await database.transaction()

    try:
        if body.name:
            if body.id:
                check = await database.execute(tags.select().where(tags.c.tag_id == body.id))
                if check == None:
                    raise HTTPException(status_code=404, detail='Tag not found')
                query = tags.update().where(tags.c.tag_id == body.id).\
                    values({tags.c.name: body.name.strip(), tags.c.updated_at: func.current_timestamp()})
                await database.execute(query=query)
                await transaction.commit()
                return body
            else:
                query = tags.insert().values(
                    name=body.name.strip(),
                    created_at=func.current_timestamp(),
                    updated_at=func.current_timestamp()
                ).returning(tags.c.tag_id, tags.c.name)
                result = await database.fetch_one(query=query)
                await transaction.commit()
                return { 'id': result.tag_id, 'name': result.name }
        else:
            raise HTTPException(status_code=400, detail='No tag name provided')
    except UniqueViolationError:
        await transaction.rollback()
        raise HTTPException(status_code=409, detail='Tag with same name already exists')
    except StringDataRightTruncationError as e:
        await transaction.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await transaction.rollback()
        raise e


@router.get('/viz/tag/{id}', response_model=Tag, tags=['viz'], responses={404: {"model": ApiErrorResponse}})
async def get_viz_tag_by_id(id: int) -> Tag:
    '''
    Find tag by ID
    '''
    result = await database.fetch_one(tags.select().where(tags.c.tag_id == id))
    if result == None:
        raise HTTPException(status_code=404, detail='Tag not found')
    else:
        return { 'id': result.tag_id, 'name': result.name }


@router.delete('/viz/tag/{id}', response_model=None, dependencies=[Depends(check_oid_authentication)], tags=['viz'])
async def delete_viz_tag(id: int) -> None:
    '''
    Deletes a tag
    '''
    try:
        async with database.transaction():
            await database.execute(tags.delete().where(tags.c.tag_id == id))
    except ForeignKeyViolationError:
        raise HTTPException(status_code=400, detail='Tag is referred to by one or more entries')

@router.get('/viz/tags', response_model=List[Tag], tags=['viz'])
async def list_viz_tags(
    time_from: Optional[datetime] = Query(None, alias='from', example='2022-06-22T18:00:00.000Z'),
    time_to: Optional[datetime] = Query(None, alias='to', example='2022-06-22T20:00:00.000Z'),
) -> List[Tag]:
    '''
    List all tags
    '''

    query = select(tags.c.tag_id.label('id'), tags.c.name)

    if time_from and time_to:
        query = query.where(between(tags.c.created_at, time_from, time_to))
    elif time_from:
        query = query.where(tags.c.created_at >= time_from)
    elif time_to:
        query = query.where(tags.c.created_at < time_to)

    return await database.fetch_all(query)
