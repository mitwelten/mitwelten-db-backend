from os import path

from sqlalchemy import select

from api.config import crd, supported_image_formats, thumbnail_size
from api.database import database
from api.dependencies import check_oid_authentication, check_oid_m2m_authentication, AuthenticationChecker, get_user
from api.tables import files_note, storage_whitelist
from api.models import PatchFile, DeleteResponse

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, Body
from fastapi.responses import StreamingResponse

from minio import Minio
from minio.error import S3Error
from minio.api import CopySource

from asyncpg.exceptions import ForeignKeyViolationError

from sqlalchemy.sql import text, func
import json

from PIL import Image
import io

router = APIRouter(tags=['storage'])

# ------------------------------------------------------------------------------
# MINIO FILE IO
# ------------------------------------------------------------------------------

storage = Minio(
    crd.minio.host,
    access_key=crd.minio.access_key,
    secret_key=crd.minio.secret_key,
)
bucket_exists = storage.bucket_exists(crd.minio.bucket)
if not bucket_exists:
    print(f'Bucket {crd.minio.bucket} does not exist.')

def stream_minio_response(response):
    try:
        while True:
            chunk = response.read(4096 * 16)
            if not chunk:
                break
            yield chunk
    finally:
        response.close()
        response.release_conn()

def get_thumbnail_name(object_name: str, image_format: str):
    """
    :param object_name: the name of the file including path and extension
    :param image_format: the mime-type of the image
    :return: standardized thumbnail file name
    """
    name = object_name.rsplit('.', 1)[0]
    return f'{name}_{thumbnail_size[0]}x{thumbnail_size[1]}.{image_format}'

@router.get('/files/walk/{object_name:path}', summary='Whitelisted media resources from S3 storage for Walk App')
async def get_walk_download(request: Request, object_name: str):
    '''
    ## Media resources for Walk App

    Requested media will be returned if path is whitelisted for public access.
    '''
    if not object_name.startswith('walk/public'):
        try:
            whitelisted = await database.fetch_one(text('select count(object_name) from prod.storage_whitelist where object_name = :object_name').\
                bindparams(object_name=object_name))
            if not whitelisted['count']:
                raise HTTPException(status_code=401, detail='Access denied')
            response = storage.get_object(crd.minio.bucket, path.splitext('scaled/' + path.basename(object_name))[0] + '.webp')
            return StreamingResponse(stream_minio_response(response), headers=response.headers)
        except S3Error as e:
            if e.code == 'NoSuchKey':
                raise HTTPException(status_code=404, detail='File not found')
    else:
        try:
            response = storage.get_object(crd.minio.bucket, object_name)
            return StreamingResponse(stream_minio_response(response), headers=response.headers)
        except S3Error as e:
            if e.code == 'NoSuchKey':
                raise HTTPException(status_code=404, detail='File not found')

@router.get('/files/discover/{object_name:path}', summary='Media resources from S3 storage')
async def get_download(request: Request, object_name: str):
    '''
    ## Media resources

    Requested media will be returned if request is authenticated and role is authorized for access or file is whitelisted.
    '''
    authenticated = False
    whitelisted = False
    auth_header = request.headers.get('authorization')
    object_name = f'discover/{object_name}'

    if auth_header:
        user = get_user(auth_header.split('Bearer ')[1])
        if user:
            authenticated = 'internal' in user['realm_access']['roles']

    if not authenticated:
        query = text('select count(object_name) from prod.storage_whitelist where object_name = :object_name').bindparams(object_name=object_name)
        whitelisted_obj = await database.fetch_one(query)
        whitelisted = whitelisted_obj['count'] > 0 if whitelisted_obj is not None else False

    if authenticated or whitelisted:
        try:
            response = storage.get_object(crd.minio.bucket, object_name)
            return StreamingResponse(stream_minio_response(response), headers=response.headers)
        except S3Error as e:
            if e.code == 'NoSuchKey':
                raise HTTPException(status_code=404, detail='File not found')
    else:
        raise HTTPException(status_code=401, detail='Access denied')

@router.patch('/files/discover/{object_name:path}', dependencies=[Depends(AuthenticationChecker(['internal']))],summary='Update media resource for discover app from S3 storage')
async def update_discover_file(object_name: str, file: PatchFile = ...):
    '''
    ## Media resources for discover app

    Media will be updated if request is authenticated and role is authorized for access.
    '''
    update_data = file.dict(exclude_unset=True)
    file_id = update_data.pop('id')
    file_type = update_data.pop('type')

    object_name = f'discover/{object_name}'
    new_object_name = update_data['object_name']

    # move file on minio if object_name has changed
    if object_name != new_object_name:
        has_thumbnail = file_type in supported_image_formats
        moving_objects = [(object_name, new_object_name)]

        if has_thumbnail:
            image_format = supported_image_formats.get(file_type)
            moving_objects.append((
                get_thumbnail_name(object_name, image_format),
                get_thumbnail_name(new_object_name, image_format)
            ))
        for source, target in moving_objects:
            try:
                storage.copy_object(
                    crd.minio.bucket,
                    target,
                    CopySource(crd.minio.bucket, source)
                )
            except S3Error as e:
                if e.code == 'NoSuchKey':
                    raise HTTPException(status_code=404, detail='File not found')

            try:
                storage.remove_object(crd.minio.bucket, source)
            except S3Error as e:
                if e.code == 'NoSuchKey':
                    # delete already copied file
                    storage.remove_object(crd.minio.bucket, target)
                    raise HTTPException(status_code=404, detail='File not found')

            # update storage_whitelist table
            if object_name.startswith('discover/public'):
                await database.execute(storage_whitelist.delete().where(storage_whitelist.c.object_name == source))
            elif new_object_name.startswith('discover/public'):
                await database.execute(storage_whitelist.insert().values({'object_name': target}))

    # update note_files table
    query = (files_note.update()
             .where(files_note.c.file_id == file_id)
             .values({**update_data, files_note.c.updated_at: func.current_timestamp()}))
    return await database.fetch_one(query)

@router.get('/files/{object_name:path}', dependencies=[Depends(check_oid_authentication)], summary='Media resources from S3 storage')
async def get_download(object_name: str):
    '''
    ## Media resources

    Requested media will be returned if request is authenticated and role is authorized for access.
    '''
    try:
        response = storage.get_object(crd.minio.bucket, object_name)
        return StreamingResponse(stream_minio_response(response), headers=response.headers)
    except S3Error as e:
        if e.code == 'NoSuchKey':
            raise HTTPException(status_code=404, detail='File not found')

@router.post('/files/discover', dependencies=[Depends(AuthenticationChecker(['internal']))])
async def post_discover_upload(file: UploadFile):
    # compose object name
    object_name = f'discover/{file.filename}'
    # make sure object doesn't already exist
    try:
        stat = storage.stat_object(crd.minio.bucket, object_name)
    except S3Error as e:
        if e.code != 'NoSuchKey':
            raise e
    else:
        return { 'object_name': stat.object_name, 'etag': stat.etag }

    # upload original size image
    upload = storage.put_object(crd.minio.bucket, object_name, file.file, length=-1, part_size=10*1024*1024)

    # if file is an image, create and upload thumbnail image
    if file.content_type in supported_image_formats:
        file.file.seek(0)
        image_format = supported_image_formats.get(file.content_type)

        try:
            content = await file.read()
            image = Image.open(io.BytesIO(content))
            image.thumbnail(thumbnail_size)
            buffer = io.BytesIO()
            image.save(buffer, format=image_format)
            buffer.seek(0)
            thumbnail_name = get_thumbnail_name(object_name, image_format)
            storage.put_object(crd.minio.bucket, thumbnail_name, buffer, length=-1, part_size=10*1024*1024)
        except Exception:
            # thumbnail is optional, no action required
            pass

    return { 'object_name': upload.object_name, 'etag': upload.etag }

@router.delete('/files/discover/{file_id}', response_model=None, dependencies=[Depends(AuthenticationChecker(['internal']))])
async def delete_tag(file_id: int) -> DeleteResponse:
    '''
    Deletes a discover file and its thumbnail if it exists.
    '''
    try:
        file = await database.fetch_one(files_note.select().where(files_note.c.file_id == file_id))
    except ForeignKeyViolationError:
        raise HTTPException(status_code=400, detail='file is referred to by one or more note records')
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    has_thumbnail = file.type in supported_image_formats
    files_to_delete = [file.object_name]

    whitelisted_obj = await database.fetch_one(
        select(func.count()).select_from(storage_whitelist).where(storage_whitelist.c.object_name == file.object_name))
    is_whitelisted = whitelisted_obj[0] > 0 if whitelisted_obj is not None else False

    if has_thumbnail:
        thumbnail_name = get_thumbnail_name(file.object_name, supported_image_formats.get(file.type))
        files_to_delete.append(thumbnail_name)
    try:
        [storage.remove_object(crd.minio.bucket, object_name) for object_name in files_to_delete]
    except S3Error as e:
        if e.code == 'NoSuchKey':
            raise HTTPException(status_code=404, detail='File not found')

    # delete entries in database
    await database.execute(files_note.delete().where(files_note.c.file_id == file_id))
    if is_whitelisted:
        for object_name in files_to_delete:
            await database.execute(storage_whitelist.delete().where(storage_whitelist.c.object_name == object_name))

    return { 'status': 'deleted', 'id': file_id }

@router.post('/files/', dependencies=[Depends(check_oid_m2m_authentication)])
async def post_upload(file: UploadFile):
    # make sure object doesn't already exist
    try:
        stat = storage.stat_object(crd.minio.bucket, file.filename)
    except S3Error as e:
        if e.code != 'NoSuchKey':
            raise e
    else:
        return { 'object_name': stat.object_name, 'etag': stat.etag }
    # upload
    upload = storage.put_object(crd.minio.bucket, file.filename, file.file, length=-1, part_size=10*1024*1024)
    return { 'object_name': upload.object_name, 'etag': upload.etag }

@router.get('/walk/imagestack_s3/{walk_id}')
async def get_imagestack_from_s3(walk_id):
    object_name = f'walk/public/{walk_id}.json'
    try:
        resp = storage.get_object(crd.minio.bucket, object_name)
        return json.loads(resp.data)
    except:
        raise HTTPException(status_code=404, detail='File not found')

@router.get('/walk/imagestacks_s3/')
async def get_imagestacks_from_s3():
    object_name = f'walk/public/'
    try:
        resp = storage.list_objects(crd.minio.bucket, object_name)
        return list(
            map(lambda p: {'path': p.object_name, 'updated_at': p.last_modified},
                filter(lambda o: path.splitext(o._object_name)[1] == '.json', resp)))
        return ['ass'] #json.loads(list(resp))
    except S3Error as e:
        print(e)
        raise HTTPException(status_code=404, detail='File not found')
