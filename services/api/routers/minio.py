from os import path

from api.config import crd
from api.database import database
from api.dependencies import check_oid_authentication, check_oid_m2m_authentication, AuthenticationChecker

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from minio import Minio
from minio.datatypes import Object
from minio.error import S3Error

from sqlalchemy.sql import text
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
            response = storage.get_object(crd.minio.bucket, path.splitext(object_name)[0] + '.webp')
            return StreamingResponse(stream_minio_response(response), headers=response.headers)
        except S3Error as e:
            if e.code == 'NoSuchKey':
                raise HTTPException(status_code=404, detail='File not found')

@router.get('/files/discover/{object_name:path}', dependencies=[Depends(AuthenticationChecker())], summary='Media resources for discover app from S3 storage')
async def get_discover_download(request: Request, object_name: str):
    '''
    ## Media resources for discover app

    Requested media will be returned if request is authenticated and role is authorized for access.
    '''
    try:
        response = storage.get_object(crd.minio.bucket, f'discover/{object_name}')
        return StreamingResponse(stream_minio_response(response), headers=response.headers)
    except S3Error as e:
        if e.code == 'NoSuchKey':
            raise HTTPException(status_code=404, detail='File not found')

@router.get('/files/{object_name:path}', dependencies=[Depends(check_oid_authentication)], summary='Media resources from S3 storage')
async def get_download(request: Request, object_name: str):
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
