from itertools import groupby
from typing import List, Optional
from datetime import datetime

from api.database import database
from api.dependencies import unique_everseen, AuthenticationChecker, get_user
from api.models import ApiErrorResponse, Note, NoteResponse, PatchNote, Tag, File
from api.tables import notes, files_note, mm_tags_notes, tags, user_entity

from asyncpg import UniqueViolationError
from fastapi import APIRouter, Depends, Query, HTTPException, Request
from sqlalchemy.sql import and_, between, select, text, func

router = APIRouter(tags=['notes', 'discover'])

# ------------------------------------------------------------------------------
# NOTES
# ------------------------------------------------------------------------------

@router.get('/notes', response_model=List[NoteResponse], response_model_exclude_none=True)
async def list_notes(
    request: Request,
    time_from: Optional[datetime] = Query(None, alias='from', example='2022-06-22T18:00:00.000Z'),
    time_to: Optional[datetime] = Query(None, alias='to', example='2022-06-22T20:00:00.000Z'),
) -> List[NoteResponse]:
    '''
    ## List all notes

    The note selection can optionally be delimited by supplying either bounded
    or unbounded ranges as a combination of `to` and `from` query parameters.
    '''

    authenticated = False
    auth_header = request.headers.get('authorization')
    if auth_header:
        user = get_user(auth_header.split('Bearer ')[1])
        if user:
            authenticated = 'public' in user['realm_access']['roles']

    query = select(notes, notes.c.created_at.label('date'), tags.c.tag_id, tags.c.name.label('tag_name'),\
            files_note.c.file_id, files_note.c.object_name, files_note.c.name.label('file_name'), files_note.c.type.label('file_type'),\
            user_entity.c.first_name.concat(' ').concat(user_entity.c.last_name).label('author')).\
        select_from(notes.outerjoin(mm_tags_notes).outerjoin(tags).outerjoin(files_note).\
            outerjoin(user_entity, user_entity.c.id == notes.c.user_sub))

    if time_from and time_to:
        query = query.where(between(notes.c.created_at, time_from, time_to))
    elif time_from:
        query = query.where(notes.c.created_at >= time_from)
    elif time_to:
        query = query.where(notes.c.created_at < time_to)

    if not authenticated:
        query = query.where(notes.c.public == True)

    # order by itertools groupby key
    query = query.order_by(notes.c.note_id)

    result = await database.fetch_all(query=query)
    output = []
    for key, grp in groupby(result, key=lambda x: x['note_id']):
        grp = list(grp)
        f_l = unique_everseen(grp, lambda x: x['file_id'])
        t_l = unique_everseen(grp, lambda x: x['tag_id'])
        e = dict(grp[0])
        e['files'] = [{'name': f['file_name'], 'object_name': f['object_name'], 'type': f['file_type']} for f in f_l if f['file_id'] != None]
        e['tags'] = [{'tag_id': t['tag_id'], 'name': t['tag_name']} for t in t_l if t['tag_id'] != None]
        output.append(e)
    return output


@router.post('/notes', dependencies=[Depends(AuthenticationChecker())], response_model=Note)
async def add_note(body: Note, auth = Depends(get_user)) -> None:
    '''
    ## Add a new note

    ### Timestamps

    The internal attribute `created_at` is used as `date` defined by the model.
    It is automatically set on creation of the record and can't be written to
    by the user.
    '''

    authorised = 'internal' in auth['realm_access']['roles']

    query = notes.insert().values(
        title=body.title,
        description=body.description,
        type=body.note_type,
        user_sub=auth.get('sub'),
        public=body.public if authorised else False, # only 'internal' can create public notes
        location=None if 'location' in body else text(f'point(:lat,:lon)').bindparams(lat=body.location.lat, lon=body.location.lon),
        created_at=body.date or func.now(),
        updated_at=func.now()
    ).returning(notes, notes.c.created_at.label('date'), notes.c.type.label('note_type'))
    return await database.fetch_one(query)

@router.get('/note/{note_id}', response_model=NoteResponse, responses={404: {'model': ApiErrorResponse}}, response_model_exclude_none=True)
async def get_note_by_id(note_id: int, request: Request) -> NoteResponse:
    '''
    Find note by ID
    '''
    authenticated = False
    auth_header = request.headers.get('authorization')
    if auth_header:
        user = get_user(auth_header.split('Bearer ')[1])
        if user:
            authenticated = 'public' in user['realm_access']['roles']

    query = select(notes, notes.c.created_at.label('date'), tags.c.tag_id, tags.c.name.label('tag_name'),
            files_note.c.file_id, files_note.c.name.label('file_name'), files_note.c.object_name, files_note.c.type.label('file_type'),
            user_entity.c.first_name.concat(' ').concat(user_entity.c.last_name).label('author')).\
        select_from(notes.outerjoin(mm_tags_notes).outerjoin(tags).outerjoin(files_note).\
            outerjoin(user_entity, user_entity.c.id == notes.c.user_sub))

    if authenticated:
        query = query.where(notes.c.note_id == note_id)
    else:
        query = query.where(and_(notes.c.note_id == note_id, notes.c.public == True))

    result = await database.fetch_all(query=query)

    if result == None or len(result) == 0:
        raise HTTPException(status_code=404, detail='Note not found')
    else:
        f_l = unique_everseen(result, lambda x: x['file_id'])
        t_l = unique_everseen(result, lambda x: x['tag_id'])
        e = dict(result[0])
        e['files'] = [{'name': f['file_name'], 'object_name': f['object_name'], 'type': f['file_type']} for f in f_l if f['file_id'] != None]
        e['tags'] = [{'id': t['tag_id'], 'name': t['tag_name']} for t in t_l if t['tag_id'] != None]
        return e

@router.patch('/note/{note_id}', response_model=Note, dependencies=[Depends(AuthenticationChecker())])
async def update_note(note_id: int, body: PatchNote = ..., auth = Depends(get_user)) -> Note:
    '''
    ## Updates a note

    Patching not implemented for `tags`, `files`
    '''
    update_data = body.dict(exclude_unset=True)

    # 'files' not implemented
    if 'files' in update_data:
        del update_data['files']

    # 'tags' not implemented
    if 'tags' in update_data:
        del update_data['tags']

    if 'note_type' in update_data:
        update_data['type'] = update_data['note_type']
        del update_data['note_type']

    del update_data['note_id']

    # only 'internal' can change public flag
    if 'internal' not in auth['realm_access']['roles']:
        del update_data['public']

    # author can't be changed
    if 'user_sub' in update_data: del update_data['user_sub']

    update_data['location'] = text('point(:lat,:lon)').bindparams(
        lat=update_data['location']['lat'],
        lon=update_data['location']['lon']
    )

    if 'date' in update_data:
        update_data['created_at'] = update_data['date']
        del update_data['date']

    query = notes.update().returning(notes, notes.c.created_at.label('date')).where(notes.c.note_id == note_id).\
        values({**update_data, notes.c.updated_at: func.current_timestamp()})

    return await database.fetch_one(query)


@router.delete('/note/{note_id}', response_model=None, dependencies=[Depends(AuthenticationChecker())])
async def delete_note(note_id: int) -> None:
    '''
    ## Deletes a note

    __potential for optimisation__: remove related records when record to be
    deleted is the last referring one.
    '''

    transaction = await database.transaction()

    try:
        await database.execute(mm_tags_notes.delete().where(mm_tags_notes.c.notes_note_id == note_id))
        await database.execute(notes.delete().where(notes.c.note_id == note_id))
    except Exception as e:
        await transaction.rollback()
        raise e
    else:
        await transaction.commit()


@router.post('/note/{note_id}/tag',tags=['tags'], response_model=None, dependencies=[Depends(AuthenticationChecker())], responses={'404': {'model': ApiErrorResponse}})
async def add_tag_to_note(note_id: int, body: Tag) -> None:
    '''
    Adds a tag for a note
    '''

    transaction = await database.transaction()

    try:
        check = await database.fetch_one(notes.select().where(notes.c.note_id == note_id))
        if check == None:
            raise HTTPException(status_code=404, detail='Note not found')

        existing_by_id = None
        existing_by_name = None
        insert_tag = None

        if body.tag_id:
            existing_by_id = await database.fetch_one(tags.select().where(tags.c.tag_id == body.tag_id))

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

        query = mm_tags_notes.insert().values({mm_tags_notes.c.tags_tag_id: insert_tag.tag_id, mm_tags_notes.c.notes_note_id: note_id})
        await database.execute(query=query)

    except UniqueViolationError:
        await transaction.rollback()
        raise HTTPException(status_code=200, detail='Tag is already assigned to this note')
    except Exception as e:
        await transaction.rollback()
        raise e
    else:
        await transaction.commit()


@router.delete('/note/{note_id}/tag', dependencies=[Depends(AuthenticationChecker())], response_model=None, tags=['tags'])
async def delete_tag_from_note(note_id: int, body: Tag) -> None:
    '''
    Deletes a tag from a note
    '''
    delete_id = None
    if body.name:
        existing = await database.fetch_one(tags.select().where(tags.c.name == body.name))
        if existing == None:
            return
        else:
            delete_id = existing.tag_id

    if body.tag_id:
        delete_id = body.tag_id

    await database.execute(mm_tags_notes.delete().where(
        and_(mm_tags_notes.c.tags_tag_id == delete_id, mm_tags_notes.c.notes_note_id == note_id)))


@router.post('/note/{note_id}/file', dependencies=[Depends(AuthenticationChecker(['internal']))], response_model=None)
async def add_file_to_note(note_id: int, body: File) -> None:
    '''
    Adds a file for a note
    '''

    # do i need this if there's a FK constraint?
    check = await database.fetch_one(notes.select().where(notes.c.note_id == note_id))
    if check == None:
        raise HTTPException(status_code=404, detail='Note not found')

    values = {
        files_note.c.note_id: note_id,
        files_note.c.object_name: body.object_name,
        files_note.c.name: body.name.strip(),
        files_note.c.type: body.type.strip(),
    }
    try:
        return await database.fetch_one(files_note.insert().values(values).returning(files_note.c.file_id))
    except UniqueViolationError:
        raise HTTPException(status_code=409, detail='File with same S3 URL already exists')


@router.delete('/file/{file_id}', dependencies=[Depends(AuthenticationChecker(['internal']))], response_model=None)
async def delete_file(file_id: int) -> None:
    '''
    Deletes a file
    '''
    await database.execute(files_note.delete().where(files_note.c.file_id == file_id))
