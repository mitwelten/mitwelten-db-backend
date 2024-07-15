from os import path
from typing import Annotated

from api.config import crd, supported_image_formats, thumbnail_size
from api.database import database
from api.dependencies import check_oid_authentication, check_oid_m2m_authentication, AuthenticationChecker

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from minio import Minio
from minio.error import S3Error

from sqlalchemy.sql import text
from uuid import uuid4
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

storage_scaled = Minio(
    crd.minio_scaled.host,
    access_key=crd.minio_scaled.access_key,
    secret_key=crd.minio_scaled.secret_key,
)
bucket_exists = storage_scaled.bucket_exists(crd.minio_scaled.bucket)
if not bucket_exists:
    print(f'Bucket {crd.minio_scaled.bucket} does not exist.')

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
            response = storage_scaled.get_object(crd.minio_scaled.bucket, path.splitext(object_name)[0] + '.webp')
            return StreamingResponse(stream_minio_response(response), headers=response.headers)
        except S3Error as e:
            if e.code == 'NoSuchKey':
                raise HTTPException(status_code=404, detail='File not found')
    else:
        # walk/public/... is whitelisted, and on unscaled server/bucket
        try:
            response = storage.get_object(crd.minio.bucket, object_name)
            return StreamingResponse(stream_minio_response(response), headers=response.headers)
        except S3Error as e:
            if e.code == 'NoSuchKey':
                raise HTTPException(status_code=404, detail='File not found')

@router.get('/tv/file/{object_name:path}', summary='Media resources for TV App from S3 storage')
async def get_tv_download(request: Request, object_name: str):
    try:
        whitelisted = await database.fetch_one(text('select count(object_name) from prod.storage_whitelist where object_name like :object_name').\
            bindparams(object_name=path.splitext(object_name)[0] + '%'))
        if not whitelisted['count']:
            raise HTTPException(status_code=401, detail='Access denied')
        response = storage_scaled.get_object(crd.minio_scaled.bucket, object_name)
        return StreamingResponse(stream_minio_response(response), headers=response.headers)
    except S3Error as e:
        if e.code == 'NoSuchKey':
            raise HTTPException(status_code=404, detail='File not found')

@router.get('/files/discover/{object_name:path}', summary='Media resources from S3 storage')
async def get_discover_file(object_name: str):
    '''
    ## Media resources

    Requested media will be returned if it exists.
    '''
    object_name = f'discover/{object_name}'
    try:
        response = storage.get_object(crd.minio.bucket, object_name)
        return StreamingResponse(stream_minio_response(response), headers=response.headers)
    except S3Error as e:
        if e.code == 'NoSuchKey':
            raise HTTPException(status_code=404, detail='File not found')


# this will work for audio files, but not for images, as they were moved to another server
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

@router.post('/files/discover', dependencies=[Depends(AuthenticationChecker(['internal']))])
async def post_discover_upload(file: UploadFile):
    '''
    ## Media resources

    Upload file to minio if request is authenticated and role is authorized for upload.
    '''
    # compose object name
    uuid = uuid4()
    object_name = f'discover/{uuid}/{file.filename}'
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
