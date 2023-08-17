from api.dependencies import AuthenticationChecker, get_user, crd

from fastapi import APIRouter, Depends, Request

router = APIRouter(tags=['auth'])

# ------------------------------------------------------------------------------
# DATA WALKING
# ------------------------------------------------------------------------------

@router.get('/login', dependencies=[Depends(AuthenticationChecker(required_roles=['public']))], tags=['authentication'])
async def login(request: Request):
    auth_header = request.headers.get('authorization')
    return get_user(auth_header.split('Bearer ')[1])

@router.get('/auth/storage', dependencies=[Depends(AuthenticationChecker(required_roles=['internal']))], tags=['authentication'])
async def get_storage_auth():
    return {
        'host': crd.minio.host,
        'bucket': crd.minio.bucket,
        'access_key': crd.minio.access_key,
        'secret_key': crd.minio.secret_key
    }
