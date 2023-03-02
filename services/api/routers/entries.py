from itertools import groupby
from typing import List, Optional
from datetime import datetime

from api.database import database
from api.dependencies import unique_everseen, check_authentication
from api.models import ApiErrorResponse, Entry, PatchEntry, Tag, File
from api.tables import entries, files_entry, mm_tags_entries, tags

from asyncpg import UniqueViolationError
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.sql import and_, between, select, text, func

router = APIRouter(tags=['entries', 'viz'])

# ------------------------------------------------------------------------------
# ENTRIES
# ------------------------------------------------------------------------------

@router.get('/entries', response_model=List[Entry], response_model_exclude_none=True)
async def list_entries(
    time_from: Optional[datetime] = Query(None, alias='from', example='2022-06-22T18:00:00.000Z'),
    time_to: Optional[datetime] = Query(None, alias='to', example='2022-06-22T20:00:00.000Z'),
) -> List[Entry]:
    '''
    ## List all entries

    The entry selection can optionally be delimited by supplying either bounded
    or unbounded ranges as a combination of `to` and `from` query parameters.
    '''

    query = select(entries, entries.c.entry_id.label('id'), entries.c.created_at.label('date'), tags.c.tag_id, tags.c.name.label('tag_name'), files_entry.c.file_id, files_entry.c.object_name, files_entry.c.name.label('file_name'), files_entry.c.type.label('file_type')).\
        select_from(entries.outerjoin(mm_tags_entries).outerjoin(tags).outerjoin(files_entry))

    if time_from and time_to:
        query = query.where(between(entries.c.created_at, time_from, time_to))
    elif time_from:
        query = query.where(entries.c.created_at >= time_from)
    elif time_to:
        query = query.where(entries.c.created_at < time_to)

    result = await database.fetch_all(query=query)
    output = []
    for key, grp in groupby(result, key=lambda x: x['id']):
        grp = list(grp)
        f_l = unique_everseen(grp, lambda x: x['file_id'])
        t_l = unique_everseen(grp, lambda x: x['tag_id'])
        e = dict(grp[0])
        e['files'] = [{'name': f['file_name'], 'link': f['object_name'], 'type': f['file_type']} for f in f_l if f['file_id'] != None]
        e['tags'] = [{'id': t['tag_id'], 'name': t['tag_name']} for t in t_l if t['tag_id'] != None]
        output.append(e)
    return output


@router.post('/entries', dependencies=[Depends(check_authentication)], response_model=Entry)
async def add_entry(body: Entry) -> None:
    '''
    ## Add a new entry to the map

    ### Timestamps

    The internal attribute `created_at` is used as `date` defined by the model.
    It is automatically set on creation of the record and can't be written to
    by the user.
    '''

    query = entries.insert().values(
        name=body.name,
        description=body.description,
        type=body.type,
        location=text(f'point(:lat,:lon)').bindparams(lat=body.location.lat, lon=body.location.lon),
        created_at=func.now(),
        updated_at=func.now()
    ).returning(entries.c.entry_id, entries.c.created_at)
    result = await database.fetch_one(query)
    return  { **body.dict(), 'id': result.entry_id, 'date': result.created_at }

@router.get('/entry/{id}', response_model=Entry, responses={404: {"model": ApiErrorResponse}}, response_model_exclude_none=True)
async def get_entry_by_id(id: int) -> Entry:
    '''
    Find entry by ID
    '''
    query = select(entries, entries.c.entry_id.label('id'), entries.c.created_at.label('date'), tags.c.tag_id, tags.c.name.label('tag_name'),
        files_entry.c.file_id, files_entry.c.name.label('file_name'), files_entry.c.object_name, files_entry.c.type.label('file_type')).\
        select_from(entries.outerjoin(mm_tags_entries).outerjoin(tags).outerjoin(files_entry)).where(entries.c.entry_id == id)
    result = await database.fetch_all(query=query)

    if result == None or len(result) == 0:
        raise HTTPException(status_code=404, detail='Entry not found')
    else:
        f_l = unique_everseen(result, lambda x: x['file_id'])
        t_l = unique_everseen(result, lambda x: x['tag_id'])
        e = dict(result[0])
        e['files'] = [{'name': f['file_name'], 'link': f['object_name'], 'type': f['file_type']} for f in f_l if f['file_id'] != None]
        e['tags'] = [{'id': t['tag_id'], 'name': t['tag_name']} for t in t_l if t['tag_id'] != None]
        return e

@router.patch('/entry/{id}', response_model=None, dependencies=[Depends(check_authentication)])
async def update_entry(id: int, body: PatchEntry = ...) -> None:
    '''
    ## Updates an entry

    Patching not implemented for `tags`, `files` and `comments`
    '''
    update_data = body.dict(exclude_unset=True)

    # 'files' not implemented
    if 'files' in update_data:
        del update_data['files']

    # 'tags' not implemented
    if 'tags' in update_data:
        del update_data['tags']

    # 'comments' not implemented
    if 'comments' in update_data:
        del update_data['comments']

    del update_data['id']

    update_data['location'] = text('point(:lat,:lon)').bindparams(
        lat=update_data['location']['lat'],
        lon=update_data['location']['lon']
    )

    update_data['created_at'] = update_data['date']
    del update_data['date']

    query = entries.update().where(entries.c.entry_id == id).\
        values({**update_data, entries.c.updated_at: func.current_timestamp()})

    return await database.execute(query)


@router.delete('/entry/{id}', response_model=None, dependencies=[Depends(check_authentication)])
async def delete_entry(id: int) -> None:
    '''
    ## Deletes an entry

    __potential for optimisation__: remove related records when record to be
    deleted is the last referring one.
    '''

    transaction = await database.transaction()

    try:
        await database.execute(mm_tags_entries.delete().where(mm_tags_entries.c.entries_entry_id == id))
        await database.execute(entries.delete().where(entries.c.entry_id == id))
    except Exception as e:
        await transaction.rollback()
        raise e
    else:
        await transaction.commit()


@router.post('/entry/{id}/tag',tags=['tags'], response_model=None, dependencies=[Depends(check_authentication)], responses={'404': {"model": ApiErrorResponse}})
async def add_tag_to_entry(id: int, body: Tag) -> None:
    '''
    Adds a tag for an entry
    '''

    transaction = await database.transaction()

    try:
        check = await database.fetch_one(entries.select().where(entries.c.entry_id == id))
        if check == None:
            raise HTTPException(status_code=404, detail='Entry not found')

        existing_by_id = None
        existing_by_name = None
        insert_tag = None

        if body.id:
            existing_by_id = await database.fetch_one(tags.select().where(tags.c.tag_id == body.id))

        if body.name:
            existing_by_name = await database.fetch_one(tags.select().where(tags.c.name == body.name))

        if existing_by_id == None and existing_by_name == None:
            if body.name:
                insert_tag = await database.fetch_one(tags.insert().values({tags.c.name: body.name.strip()}).returning(tags.c.tag_id))
            else:
                raise HTTPException(status_code=404, detail='Tag not found')
        elif existing_by_id:
            insert_tag = existing_by_id
        elif existing_by_name:
            insert_tag = existing_by_name

        query = mm_tags_entries.insert().values({mm_tags_entries.c.tags_tag_id: insert_tag.tag_id, mm_tags_entries.c.entries_entry_id: id})
        await database.execute(query=query)

    except UniqueViolationError:
        await transaction.rollback()
        raise HTTPException(status_code=200, detail='Tag is already assigned to this entry')
    except Exception as e:
        await transaction.rollback()
        raise e
    else:
        await transaction.commit()


@router.delete('/entry/{id}/tag', dependencies=[Depends(check_authentication)], response_model=None, tags=['tags'])
async def delete_tag_from_entry(id: int, body: Tag) -> None:
    '''
    Deletes a tag from an entry
    '''
    delete_id = None
    if body.name:
        existing = await database.fetch_one(tags.select().where(tags.c.name == body.name))
        if existing == None:
            return
        else:
            delete_id = existing.tag_id

    if body.id:
        delete_id = body.id

    await database.execute(mm_tags_entries.delete().where(
        and_(mm_tags_entries.c.tags_tag_id == delete_id, mm_tags_entries.c.entries_entry_id == id)))


@router.post('/entry/{entry_id}/file', dependencies=[Depends(check_authentication)], response_model=None, tags=['files'])
async def add_file_to_entry(entry_id: int, body: File) -> None:
    '''
    Adds a file for an entry
    '''

    # do i need this if there's a FK constraint?
    check = await database.fetch_one(entries.select().where(entries.c.entry_id == entry_id))
    if check == None:
        raise HTTPException(status_code=404, detail='Entry not found')

    values = {
        files_entry.c.entry_id: entry_id,
        files_entry.c.object_name: body.link,
        files_entry.c.name: body.name.strip(),
        files_entry.c.type: body.type.strip(),
    }
    try:
        return await database.fetch_one(files_entry.insert().values(values).returning(files_entry.c.file_id))
    except UniqueViolationError:
        raise HTTPException(status_code=409, detail='File with same S3 URL already exists')


@router.delete('/file/{id}', dependencies=[Depends(check_authentication)], response_model=None, tags=['files'])
async def delete_file(file_id: int) -> None:
    '''
    Deletes a file
    '''
    await database.execute(files_entry.delete().where(files_entry.c.file_id == file_id))
