import sys
from typing import List, Union
from datetime import datetime

from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import conint, constr

import databases
from sqlalchemy.sql import select, func, between, and_
from asyncpg.exceptions import UniqueViolationError, StringDataRightTruncationError, ForeignKeyViolationError

from models import ApiResponse, DatumResponse, Entry, PatchEntry, Node, Tag, ApiErrorResponse, PaxDatum, EnvDatum, File
from tables import entry, location, tag, mm_tag_entry, node, datum_pax, datum_env, file

sys.path.append('../../')
import credentials as crd

#
# Set up database
#

DATABASE_URL = f'postgresql://{crd.db.user}:{crd.db.password}@{crd.db.host}/{crd.db.database}'

database = databases.Database(DATABASE_URL)

#
# Set up FastAPI
#

origins = [
    'https://viz.mitwelten.org',    # production environment
    'http://localhost',             # dev environment
    'http://localhost:4200',        # angular dev environment
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
    version='1.0.0',
    servers=[
        {'url': 'https://data.mitwelten.org/viz/v1', 'description': 'Production environment'},
        {'url': 'http://localhost:8000', 'description': 'Development environment'}
    ],
    root_path='/viz/v1',
    root_path_in_servers=False,
    openapi_tags=tags_metadata
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
        select_from(target.outerjoin(node)) # .outerjoin(location) # not required atm

    node_selection = target.c.node_id == typecheck['node_id']

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

@app.get('/entries', response_model=List[Entry], tags=['entry'])
async def list_entries(
    time_from: Optional[datetime] = Query(None, alias='from', example='2022-06-22T18:00:00.000Z'),
    time_to: Optional[datetime] = Query(None, alias='to', example='2022-06-22T20:00:00.000Z'),
) -> List[Entry]:
    '''
    ## List all entries

    The entry selection can optionally be delimited by supplying either bounded
    or unbounded ranges as a combination of `to` and `from` query parameters.

    ### Locations

    `locations` reside in a dedicated table, and are joined. The foreign key
    is omitted in the response.
    '''

    query = select(entry, entry.c.entry_id.label('id'), entry.c.created_at.label('date'), location.c.location, tag.c.tag_id, tag.c.name.label('tag_name')).\
        select_from(entry.outerjoin(location).outerjoin(mm_tag_entry).outerjoin(tag))

    if time_from and time_to:
        query = query.where(between(entry.c.created_at, time_from, time_to))
    elif time_from:
        query = query.where(entry.c.created_at >= time_from)
    elif time_to:
        query = query.where(entry.c.created_at < time_to)

    result = await database.fetch_all(query=query)
    entry_map = {}
    for item in result:
        if item['id'] in entry_map:
            # add tags to array
            d = {**item._mapping}
            entry_map[item['id']]['tags'].append({'id':d['tag_id'], 'name':d['tag_name']})
        else:
            d = {**item._mapping}
            d['location'] = item['location']
            if d['tag_id'] != None:
                d['tags'] = [{'id':d['tag_id'], 'name':d['tag_name']}]
            entry_map[item['id']] = d
    return list(entry_map.values())


@app.post('/entries', response_model=Entry, tags=['entry'])
async def add_entry(body: Entry) -> None:
    '''
    ## Add a new entry to the map

    ### Locations

    `locations` reside in a dedicated table, new `entry` records are created
    trying to find a `location` that is within a radius of ~1m. If such a
    record is found, the closest one is referenced in the new `entry` record.
    If no location is found, a new one is created, with `type` = 'user-created',
    and referenced in the new `entry` record.

    ### Timestamps

    The internal attribute `created_at` is used as `date` defined by the model.
    It is automatically set on creation of the record and can't be written to
    by the user.
    '''

    transaction = await database.transaction()

    try:
        point = f'point({float(body.location.lat)}, {float(body.location.lon)})'
        thresh_1m = 0.0000115
        # thresh_1m = 0.02
        location_query = f'''
        select location_id from {crd.db.schema}.locations
        where location <-> {point} < {thresh_1m}
        order by location <-> {point}
        limit 1
        '''
        result = await database.fetch_one(query=location_query)

        location_id = None
        if result == None:
            loc_insert_query = f'''
            insert into {crd.db.schema}.locations(location, type)
            values (point({body.location.lat},{body.location.lon}), 'user-added')
            returning location_id
            '''
            location_id = await database.execute(loc_insert_query)
        else:
            location_id = result.location_id

        query = entry.insert().values(
            name=body.name,
            description=body.description,
            type=body.type,
            location_id=location_id,
            created_at=func.now(),
            updated_at=func.now()
        ).returning(entry.c.entry_id, entry.c.created_at)
        result = await database.fetch_one(query)

    except Exception as e:
        await transaction.rollback()
        raise e
    else:
        await transaction.commit()
        return  { **body.dict(), 'id': result.entry_id, 'date': result.created_at }

@app.get('/entry/{id}', response_model=Entry, tags=['entry'], responses={404: {"model": ApiErrorResponse}})
async def get_entry_by_id(id: int) -> Entry:
    '''
    Find entry by ID
    '''
    query = select(entry, entry.c.entry_id.label('id'), entry.c.created_at.label('date'), location.c.location, tag.c.tag_id, tag.c.name.label('tag_name'),
        file.c.file_id, file.c.name, file.c.object_name, file.c.type).\
        select_from(entry.outerjoin(location).outerjoin(mm_tag_entry).outerjoin(tag).outerjoin(file)).where(entry.c.entry_id == id)
    result = await database.fetch_all(query=query)

    if result == None:
        raise HTTPException(status_code=404, detail='Entry not found')
    else:
        entry_map = None
        for item in result:
            if entry_map:
                # add tags to array
                entry_map['tags'].append({'id':item['tag_id'], 'name':item['tag_name']})
                # add files to array
                entry_map['files'].append({'id':item['file_id'], 'name':item['name'], 'link':item['object_name'], 'type':item['type']})
            else:
                entry_map = {**item._mapping}
                entry_map['location'] = item['location']
                if item['tag_id'] != None:
                    entry_map['tags'] = [{'id':item['tag_id'], 'name':item['tag_name']}]
                if item['file_id'] != None:
                    entry_map['files'] = [{'id':item['file_id'], 'name':item['name'], 'link':item['object_name'], 'type':item['type']}]

        # reduce cardinality duplication
        if 'tags' in entry_map:
            entry_map['tags'] = [next((e for e in entry_map['tags'] if e['id'] == i)) for i in {t['id'] for t in entry_map['tags']}]
        if 'files' in entry_map:
            entry_map['files'] = [next((e for e in entry_map['files'] if e['id'] == i)) for i in {f['id'] for f in entry_map['files']}]

        return entry_map

@app.patch('/entry/{id}', response_model=None, tags=['entry'])
async def update_entry(id: int, body: PatchEntry = ...) -> None:
    '''
    ## Updates an entry

    Patching not implemented for `tags` and `files`

    ### Locations

    The record is updated with the closest `location` in a radius of ~1m. If
    no `location` is found, a new one is created and referenced.
    '''
    update_data = body.dict(exclude_unset=True)

    transaction = await database.transaction()

    try:
        location_id = None
        if 'location' in update_data:
            point = f'point({float(body.location.lat)}, {float(body.location.lon)})'
            thresh_1m = 0.0000115
            location_query = f'''
            select location_id from {crd.db.schema}.locations
            where location <-> {point} < {thresh_1m}
            order by location <-> {point}
            limit 1
            '''
            result = await database.fetch_one(query=location_query)

            if result == None:
                loc_insert_query = f'''
                insert into {crd.db.schema}.locations(location, type)
                values (point({body.location.lat},{body.location.lon}), 'user-added')
                returning location_id
                '''
                location_id = await database.execute(loc_insert_query)
            else:
                location_id = result.location_id
            update_data['location_id'] = location_id
            del update_data['location']

        query = entry.update().where(entry.c.entry_id == id).\
            values({**update_data, entry.c.updated_at: func.current_timestamp()})

        result = await database.execute(query)

    except Exception as e:
        await transaction.rollback()
        raise e
    else:
        await transaction.commit()
        return result


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
        await database.execute(file.delete().where(file.c.file_id == id))
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
    return await database.fetch_one(file.insert().values(values).returning(file.c.file_id))

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
    List all nodes

    This is a temporary, hacky, but working implementation. It becomes obvious
    that the database schema requires an abstraction of `deployment`.
    '''

    select_part = f'''
    select nl.node_id, node_label, n.type as node_type, n.description as node_description, platform,
    nl.location_id, location, name as location_name, l.description as location_description, l.type as location_type
    from node_locations nl
    left join {crd.db.schema}.nodes n on n.node_id = nl.node_id
    left join {crd.db.schema}.locations l on l.location_id = nl.location_id
    '''
    query = ''
    values = {}

    if time_from and time_to:
        query = f'''
        with node_locations as (
            select distinct node_id, location_id from {crd.db.schema}.files_image
            where location_id is not null and time between :time_from and :time_to
            union
            select distinct node_id, location_id from {crd.db.schema}.files_audio
            where location_id is not null and (time + (duration || ' seconds')::interval) > :time_from and time < :time_to
        )'''
        values = { 'time_from': time_from, 'time_to': time_to }
    elif time_from:
        query = f'''
        with node_locations as (
            select distinct node_id, location_id from {crd.db.schema}.files_image
            where location_id is not null and time >= :time_from
            union
            select distinct node_id, location_id from {crd.db.schema}.files_audio
            where location_id is not null and (time + (duration || ' seconds')::interval) > :time_from
        )'''
        values = { 'time_from': time_from }
    elif time_to:
        query = f'''
        with node_locations as (
            select distinct node_id, location_id from {crd.db.schema}.files_image
            where location_id is not null and time < :time_to
            union
            select distinct node_id, location_id from {crd.db.schema}.files_audio
            where location_id is not null and (time + (duration || ' seconds')::interval) <= :time_to
        )'''
        values = { 'time_to': time_to }
    else:
        query = f'''
        with node_locations as (
            select distinct node_id, location_id from {crd.db.schema}.files_image
            where location_id is not null
            union
            select distinct node_id, location_id from {crd.db.schema}.files_audio
            where location_id is not null
        )'''

    query += select_part
    result = await database.fetch_all(query=query, values=values)
    transform = []
    for record in result:
        transform.append({
            'id': record.node_id,
            'name': record.node_label,
            'description': record.node_description,
            'platform': record.platform,
            'type': record.node_type,
            'location': {
                'id': record.location_id,
                'location': {
                    'lat': record.location[0],
                    'lon': record.location[1]
                },
                'type': record.location_type,
                'name': record.location_name,
                'description': record.location_description
            }
        })
    return transform


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
