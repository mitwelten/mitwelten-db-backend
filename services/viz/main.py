from itertools import filterfalse, groupby
from pprint import pprint
import sys
from typing import List, Union
from datetime import datetime

from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, Query, HTTPException
from pydantic import conint, constr

import databases
from sqlalchemy.sql import select, func, between, and_, text, LABEL_STYLE_TABLENAME_PLUS_COL
from asyncpg.exceptions import UniqueViolationError, StringDataRightTruncationError, ForeignKeyViolationError

from models import ApiResponse, DatumResponse, Entry, PatchEntry, Node, Tag, ApiErrorResponse, PaxDatum, EnvDatum, File
from tables import entry, tag, mm_tag_entry, node, datum_pax, datum_env, file, deployment

sys.path.append('../../')
import credentials as crd

#
# Set up database
#

DATABASE_URL = f'postgresql://{crd.db.user}:{crd.db.password}@{crd.db.host}/{crd.db.database}'

database = databases.Database(DATABASE_URL, min_size=5, max_size=10)

#
# Set up FastAPI
#

origins = [
    'https://viz.mitwelten.org',    # production environment
    'http://localhost',             # dev environment
]

tags_metadata = [
    {
        'name': 'entry',
        'description': 'Pins, added to the map',
    },
    {
        'name': 'node',
        'description': 'Deployed devices',
    },
    {
        'name': 'tag',
        'description': 'Tags',
    },
    {
        'name': 'datum',
        'description': 'Sensor / Capture Data',
    },
    {
        'name': 'file',
        'description': 'Files uploaded for / added to entries',
    },
]

app = FastAPI(
    title='Mitwelten REST API',
    description='This service provides REST endpoints to exchange data from [Mitwelten](https://mitwelten.org) for the purpose of visualisation and map plotting.',
    contact={'email': 'mitwelten.technik@fhnw.ch'},
    version='2.0.0',
    servers=[
        {'url': 'https://data.mitwelten.org/viz/v2', 'description': 'Production environment'},
        {'url': 'http://localhost:8000', 'description': 'Development environment'}
    ],
    root_path='/viz/v2',
    root_path_in_servers=False,
    openapi_tags=tags_metadata
)

if crd.DEV == True:
    from fastapi.middleware.cors import CORSMiddleware
    app.root_path = '/'
    app.root_path_in_servers=True
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
)

@app.on_event('startup')
async def startup():
    await database.connect()

@app.on_event('shutdown')
async def shutdown():
    await database.disconnect()

#
# Endpoint Implementations
#

@app.get('/data/{node_label}', response_model=DatumResponse, tags=['datum'])
async def list_data(
    node_label: constr(regex=r'\d{4}-\d{4}'),
    time_from: Optional[datetime] = Query(None, alias='from', example='2022-06-22T18:00:00.000Z'),
    time_to: Optional[datetime] = Query(None, alias='to', example='2022-06-22T20:00:00.000Z'),
    limit: Optional[conint(ge=1, le=65536)] = 32768,
) -> DatumResponse:
    '''
    List sensor / capture data in timestamp ascending order
    '''
    typecheck = await database.fetch_one(select(node.c.node_id, node.c.type).where(node.c.node_label == node_label))
    if typecheck == None:
        raise HTTPException(status_code=404, detail='Node not found')

    # select the target table
    target = None
    if typecheck['type'] in ['pax', 'Pax']:
        target = datum_pax
        typeclass = PaxDatum
    elif typecheck['type'] in ['env', 'HumiTemp', 'HumiTempMoisture', 'Moisture']:
        target = datum_env
        typeclass = EnvDatum
    else:
        raise HTTPException(status_code=400, detail='Invalid node type: {}'.format(typecheck['type']))

    # define the join
    query = select(target, node.c.node_label.label('nodeLabel')).\
        select_from(target.outerjoin(deployment).outerjoin(node))

    node_selection = node.c.node_id == typecheck['node_id']

    # define time range criteria
    if time_from and time_to:
        query = query.where(node_selection, between(target.c.time, time_from, time_to))
    elif time_from:
        query = query.where(node_selection, target.c.time >= time_from)
    elif time_to:
        query = query.where(node_selection, target.c.time < time_to)
    else:
        query = query.where(node_selection)

    result = await database.fetch_all(query=query.order_by(target.c.time))
    typed_result = []
    for datum in result:
        typed_result.append(typeclass(type=typecheck['type'], **datum))
    return typed_result

def unique_everseen(iterable, key=None):
    '''List unique elements, preserving order. Remember all elements ever seen.'''
    seen = set()
    seen_add = seen.add
    if key is None:
        for element in filterfalse(seen.__contains__, iterable):
            seen_add(element)
            yield element
    else:
        for element in iterable:
            k = key(element)
            if k not in seen:
                seen_add(k)
                yield element

@app.get('/entries', response_model=List[Entry], tags=['entry'], response_model_exclude_none=True)
async def list_entries(
    time_from: Optional[datetime] = Query(None, alias='from', example='2022-06-22T18:00:00.000Z'),
    time_to: Optional[datetime] = Query(None, alias='to', example='2022-06-22T20:00:00.000Z'),
) -> List[Entry]:
    '''
    ## List all entries

    The entry selection can optionally be delimited by supplying either bounded
    or unbounded ranges as a combination of `to` and `from` query parameters.
    '''

    query = select(entry, entry.c.entry_id.label('id'), entry.c.created_at.label('date'), tag.c.tag_id, tag.c.name.label('tag_name'), file.c.file_id, file.c.object_name, file.c.name.label('file_name'), file.c.type.label('file_type')).\
        select_from(entry.outerjoin(mm_tag_entry).outerjoin(tag).outerjoin(file))

    if time_from and time_to:
        query = query.where(between(entry.c.created_at, time_from, time_to))
    elif time_from:
        query = query.where(entry.c.created_at >= time_from)
    elif time_to:
        query = query.where(entry.c.created_at < time_to)

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


@app.post('/entries', response_model=Entry, tags=['entry'])
async def add_entry(body: Entry) -> None:
    '''
    ## Add a new entry to the map

    ### Timestamps

    The internal attribute `created_at` is used as `date` defined by the model.
    It is automatically set on creation of the record and can't be written to
    by the user.
    '''

    query = entry.insert().values(
        name=body.name,
        description=body.description,
        type=body.type,
        location=text(f'point(:lat,:lon)').bindparams(lat=body.location.lat, lon=body.location.lon),
        created_at=func.now(),
        updated_at=func.now()
    ).returning(entry.c.entry_id, entry.c.created_at)
    result = await database.fetch_one(query)
    return  { **body.dict(), 'id': result.entry_id, 'date': result.created_at }

@app.get('/entry/{id}', response_model=Entry, tags=['entry'], responses={404: {"model": ApiErrorResponse}}, response_model_exclude_none=True)
async def get_entry_by_id(id: int) -> Entry:
    '''
    Find entry by ID
    '''
    query = select(entry, entry.c.entry_id.label('id'), entry.c.created_at.label('date'), tag.c.tag_id, tag.c.name.label('tag_name'),
        file.c.file_id, file.c.name.label('file_name'), file.c.object_name, file.c.type.label('file_type')).\
        select_from(entry.outerjoin(mm_tag_entry).outerjoin(tag).outerjoin(file)).where(entry.c.entry_id == id)
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

@app.patch('/entry/{id}', response_model=None, tags=['entry'])
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

    query = entry.update().where(entry.c.entry_id == id).\
        values({**update_data, entry.c.updated_at: func.current_timestamp()})

    return await database.execute(query)


@app.delete('/entry/{id}', response_model=None, tags=['entry'])
async def delete_entry(id: int) -> None:
    '''
    ## Deletes an entry

    __potential for optimisation__: remove related records when record to be
    deleted is the last referring one.
    '''

    transaction = await database.transaction()

    try:
        await database.execute(mm_tag_entry.delete().where(mm_tag_entry.c.entries_entry_id == id))
        await database.execute(entry.delete().where(entry.c.entry_id == id))
    except Exception as e:
        await transaction.rollback()
        raise e
    else:
        await transaction.commit()


@app.post('/entry/{id}/tag',tags=['entry', 'tag'], response_model=None, responses={'404': {"model": ApiErrorResponse}})
async def add_tag_to_entry(id: int, body: Tag) -> None:
    '''
    Adds a tag for an entry
    '''

    transaction = await database.transaction()

    try:
        check = await database.fetch_one(entry.select().where(entry.c.entry_id == id))
        if check == None:
            raise HTTPException(status_code=404, detail='Entry not found')

        existing_by_id = None
        existing_by_name = None
        insert_tag = None

        if body.id:
            existing_by_id = await database.fetch_one(tag.select().where(tag.c.tag_id == body.id))

        if body.name:
            existing_by_name = await database.fetch_one(tag.select().where(tag.c.name == body.name))

        if existing_by_id == None and existing_by_name == None:
            if body.name:
                insert_tag = await database.fetch_one(tag.insert().values({tag.c.name: body.name.strip()}).returning(tag.c.tag_id))
            else:
                raise HTTPException(status_code=404, detail='Tag not found')
        elif existing_by_id:
            insert_tag = existing_by_id
        elif existing_by_name:
            insert_tag = existing_by_name

        query = mm_tag_entry.insert().values({mm_tag_entry.c.tags_tag_id: insert_tag.tag_id, mm_tag_entry.c.entries_entry_id: id})
        await database.execute(query=query)

    except UniqueViolationError:
        await transaction.rollback()
        raise HTTPException(status_code=200, detail='Tag is already assigned to this entry')
    except Exception as e:
        await transaction.rollback()
        raise e
    else:
        await transaction.commit()


@app.delete('/entry/{id}/tag',tags=['entry', 'tag'], response_model=None)
async def delete_tag_from_entry(id: int, body: Tag) -> None:
    '''
    Deletes a tag from an entry
    '''
    delete_id = None
    if body.name:
        existing = await database.fetch_one(tag.select().where(tag.c.name == body.name))
        if existing == None:
            return
        else:
            delete_id = existing.tag_id

    if body.id:
        delete_id = body.id

    await database.execute(mm_tag_entry.delete().where(
        and_(mm_tag_entry.c.tags_tag_id == delete_id, mm_tag_entry.c.entries_entry_id == id)))


@app.post('/entry/{entry_id}/file', response_model=None, tags=['entry', 'file'])
async def add_file_to_entry(entry_id: int, body: File) -> None:
    '''
    Adds a file for an entry
    '''

    # do i need this if there's a FK constraint?
    check = await database.fetch_one(entry.select().where(entry.c.entry_id == entry_id))
    if check == None:
        raise HTTPException(status_code=404, detail='Entry not found')

    values = {
        file.c.entry_id: entry_id,
        file.c.object_name: body.link,
        file.c.name: body.name.strip(),
        file.c.type: body.type.strip(),
    }
    try:
        return await database.fetch_one(file.insert().values(values).returning(file.c.file_id))
    except UniqueViolationError:
        raise HTTPException(status_code=409, detail='File with same S3 URL already exists')


@app.delete('/file/{id}', response_model=None, tags=['file'])
async def delete_file(file_id: int) -> None:
    '''
    Deletes a file
    '''
    await database.execute(file.delete().where(file.c.file_id == file_id))

@app.get('/nodes', response_model=List[Node], tags=['node'])
async def list_nodes(
    time_from: Optional[datetime] = Query(None, alias='from', example='2021-09-01T00:00:00.000Z'),
    time_to: Optional[datetime] = Query(None, alias='to', example='2022-08-31T23:59:59.999Z'),
) -> List[Node]:
    '''
    List all deployed nodes
    '''

    query = select(deployment.alias('d').outerjoin(node.alias('n'))).\
        set_label_style(LABEL_STYLE_TABLENAME_PLUS_COL)

    # define time range criteria
    if time_from and time_to:
        query = query.where(text("n.type != 'Test'"), text("d.period && tstzrange(:time_from, :time_to)").bindparams(time_from=time_from, time_to=time_to))
    elif time_from:
        query = query.where(text("n.type != 'Test'"), text("d.period && tstzrange(:time_from, 'infinity')").bindparams(time_from=time_from))
    elif time_to:
        query = query.where(text("n.type != 'Test'"), text("d.period && tstzrange('-infinity', :time_to)").bindparams(time_to=time_to))
    else:
        query = query.where(text("n.type != 'Test'"))

    result = await database.fetch_all(query)
    return [{
        'id': r['n_node_id'],
        'name': r['n_node_label'],
        'location': r['d_location'],
        'location_description': r['d_description'],
        'type': r['n_type'],
        'platform': r['n_platform'],
        'description': r['n_description'],
    } for r in result]


@app.put('/tag', response_model=None, tags=['tag'], responses={
        400: {"model": ApiErrorResponse},
        404: {"model": ApiErrorResponse},
        409: {"model": ApiErrorResponse}})
async def put_tag(body: Tag) -> None:
    '''
    Add a new tag or update an existing one
    '''

    transaction = await database.transaction()

    try:
        if body.name:
            if body.id:
                check = await database.execute(tag.select().where(tag.c.tag_id == body.id))
                if check == None:
                    raise HTTPException(status_code=404, detail='Tag not found')
                query = tag.update().where(tag.c.tag_id == body.id).\
                    values({tag.c.name: body.name.strip(), tag.c.updated_at: func.current_timestamp()})
                await database.execute(query=query)
                await transaction.commit()
                return body
            else:
                query = tag.insert().values(
                    name=body.name.strip(),
                    created_at=func.current_timestamp(),
                    updated_at=func.current_timestamp()
                ).returning(tag.c.tag_id, tag.c.name)
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


@app.get('/tag/{id}', response_model=Tag, tags=['tag'], responses={404: {"model": ApiErrorResponse}})
async def get_tag_by_id(id: int) -> Tag:
    '''
    Find tag by ID
    '''
    result = await database.fetch_one(tag.select().where(tag.c.tag_id == id))
    if result == None:
        raise HTTPException(status_code=404, detail='Tag not found')
    else:
        return { 'id': result.tag_id, 'name': result.name }


@app.delete('/tag/{id}', response_model=None, tags=['tag'])
async def delete_tag(id: int) -> None:
    '''
    Deletes a tag
    '''
    try:
        async with database.transaction():
            await database.execute(tag.delete().where(tag.c.tag_id == id))
    except ForeignKeyViolationError:
        raise HTTPException(status_code=400, detail='Tag is referred to by one or more entries')

@app.get('/tags', response_model=List[Tag], tags=['tag'])
async def list_tags(
    time_from: Optional[datetime] = Query(None, alias='from', example='2022-06-22T18:00:00.000Z'),
    time_to: Optional[datetime] = Query(None, alias='to', example='2022-06-22T20:00:00.000Z'),
) -> List[Tag]:
    '''
    List all tags
    '''

    query = select(tag.c.tag_id.label('id'), tag.c.name)

    if time_from and time_to:
        query = query.where(between(tag.c.created_at, time_from, time_to))
    elif time_from:
        query = query.where(tag.c.created_at >= time_from)
    elif time_to:
        query = query.where(tag.c.created_at < time_to)

    return await database.fetch_all(query)
