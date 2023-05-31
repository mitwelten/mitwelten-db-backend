from api.database import database
from fastapi import APIRouter, Depends, Request, HTTPException, status
from api.dependencies import check_oid_authentication, get_user
from sqlalchemy.sql import select, text
from api.tables import user_collections
from api.models import Annotation
from typing import List
import json
import credentials as crd


router = APIRouter(tags=['explore'])

# ------------------------------------------------------------------------------
# Explore routes
# ------------------------------------------------------------------------------

@router.get('/explore/collection', dependencies=[Depends(check_oid_authentication)])
async def get_collection(request: Request):
    auth_header = request.headers.get("authorization")
    if auth_header is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Authentication failed',
            headers={'WWW-Authenticate': 'Bearer'},
        )
    user = get_user(auth_header.split("Bearer ")[1])
    user_sub = user.get("sub")
    if user_sub is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Authentication failed',
            headers={'WWW-Authenticate': 'Bearer'},
        )
    query = select(user_collections.c.datasets).where(user_collections.c.user_sub == user_sub)
    result = await database.fetch_one(query)
    if "datasets" in dict(result):
        return dict(result).get("datasets")
    return []

@router.post('/explore/collection', dependencies=[Depends(check_oid_authentication)])
async def get_collection(collection: List[dict], request: Request):
    auth_header = request.headers.get("authorization")
    if auth_header is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Authentication failed',
            headers={'WWW-Authenticate': 'Bearer'},
        )
    user = get_user(auth_header.split("Bearer ")[1])
    user_sub = user.get("sub")
    if user_sub is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Authentication failed',
            headers={'WWW-Authenticate': 'Bearer'},
        )
    
    transaction = await database.transaction()

    try:
        query = text(f"""
    INSERT INTO {crd.db.schema}.user_collections ("user_sub", "datasets")
    VALUES (:user_sub, :datasets)
    ON CONFLICT ("user_sub") DO UPDATE
    SET "datasets" = EXCLUDED."datasets"
    """).bindparams(user_sub = user_sub, datasets = json.dumps(collection))
        await database.execute(query)

    except Exception as e:
        await transaction.rollback()
        print(str(e))
        raise HTTPException(status_code=409, detail=str(e))

    else:
        await transaction.commit()
        return True