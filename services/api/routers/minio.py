
from api.config import crd
from api.dependencies import check_oid_authentication

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from minio import Minio
from minio.error import S3Error

router = APIRouter(tags=['files', 's3'])

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
            chunk = response.read(4096)
            if not chunk:
                break
            yield chunk
    finally:
        response.close()
        response.release_conn()

@router.get('/files/{object_name:path}', dependencies=[Depends(check_oid_authentication)])
async def get_download(request: Request, object_name: str):
    try:
        response = storage.get_object(crd.minio.bucket, object_name)
        return StreamingResponse(stream_minio_response(response), headers=response.headers)
    except S3Error as e:
        if e.code == 'NoSuchKey':
            raise HTTPException(status_code=404, detail='File not found')

'''
whitelist
- datetyp
    - jpgeg: ok

    - wav: nok

gbif db: gbif table
'''
