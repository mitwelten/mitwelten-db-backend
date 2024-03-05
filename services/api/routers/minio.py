from os import path
from typing import Annotated

from api.config import crd
from api.database import database
from api.dependencies import check_oid_authentication, check_oid_m2m_authentication, AuthenticationChecker, get_user
from api.tables import files_note, storage_whitelist
from api.models import PatchFile

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, Body
from fastapi.responses import StreamingResponse

from minio import Minio
from minio.error import S3Error
from minio.api import CopySource

from sqlalchemy.sql import text, func
import json

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
        query = text('select count(object_name) from dev.storage_whitelist where object_name = :object_name').bindparams(object_name=object_name)
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
    # upload
    upload = storage.put_object(crd.minio.bucket, object_name, file.file, length=-1, part_size=10*1024*1024)
    return { 'object_name': upload.object_name, 'etag': upload.etag }

@router.patch('/files/discover/{object_name:path}', dependencies=[Depends(AuthenticationChecker(['internal']))], summary='Update media resource for discover app from S3 storage')
async def update_discover_file(object_name: str, file: PatchFile = ...):
    '''
    ## Media resources for discover app

    Media will be updated if request is authenticated and role is authorized for access.
    '''
    update_data = file.dict(exclude_unset=True)
    file_id = update_data["id"]
    del update_data["id"]

    object_name = f'discover/{object_name}'
    new_object_name = update_data["object_name"]

    # move file on minio if object_name has changed
    if object_name != new_object_name:
        # TODO move thumbnail
        try:
            storage.copy_object(
                crd.minio.bucket,
                new_object_name,
                CopySource(crd.minio.bucket, object_name)
            )
        except S3Error as e:
            if e.code == 'NoSuchKey':
                raise HTTPException(status_code=404, detail='File not found')

        try:
            storage.remove_object(crd.minio.bucket, object_name)
        except S3Error as e:
            if e.code == 'NoSuchKey':
                # delete already copied file
                storage.remove_object(crd.minio.bucket, new_object_name)
                raise HTTPException(status_code=404, detail='File not found')

        # update storage_whitelist table
        if object_name.startswith('discover/public'):
            await database.execute(storage_whitelist.delete().where(storage_whitelist.c.object_name == object_name))
        elif new_object_name.startswith('discover/public'):
            await database.execute(storage_whitelist.insert().values({'object_name': new_object_name}))

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
