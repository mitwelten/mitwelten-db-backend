from api.database import database
from fastapi import APIRouter, Depends, Request, HTTPException, status
from api.dependencies import get_user, AuthenticationChecker
from sqlalchemy.sql import select, text, insert, delete, and_, update
from api.tables import user_collections, annotations, user_entity
from api.models import AnnotationText, AnnotationContent, Annotation
from typing import List
import json
import credentials as crd


router = APIRouter(tags=['explore'])

# ------------------------------------------------------------------------------
# Explore routes
# ------------------------------------------------------------------------------

@router.get('/explore/collection')
async def get_collection(request: Request, is_allowed: bool = Depends(AuthenticationChecker())):
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
    if result is not None:
        if "datasets" in dict(result):
            return dict(result).get("datasets")
    return []

@router.post('/explore/collection')
async def post_collection(collection: List[dict], request: Request, is_allowed: bool = Depends(AuthenticationChecker())):
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

@router.get('/explore/annotations',  response_model=List[Annotation])
async def get_annotation_list(is_allowed: bool = Depends(AuthenticationChecker())) -> List[Annotation]:
    query = select(annotations,  user_entity.c.first_name, user_entity.c.last_name, user_entity.c.username)\
        .select_from(annotations)\
        .outerjoin(user_entity, user_entity.c.id == annotations.c.user_sub)
    results = await database.fetch_all(query)
    return [
        Annotation(
            title=r.title,
            user_sub=r.user_sub,
            created_at=r.created_at,
            updated_at=r.updated_at,
            content=r.content,
            url=r.url,
            datasets=r.datasets,
            full_name=f'{r.first_name} {r.last_name}'
            if r.first_name is not None and r.last_name is not None
            else "Mitwelten User",
            username=r.username if r.username is not None else "mitwelten",
            id=r.annot_id
        )
        for r in results
        ]

@router.get('/explore/annotations/{annot_id}', response_model=Annotation)
async def get_annotation_by_id(annot_id: int, is_allowed: bool = Depends(AuthenticationChecker())) -> Annotation:
    query = select(annotations,  user_entity.c.first_name, user_entity.c.last_name, user_entity.c.username)\
        .select_from(annotations)\
        .outerjoin(user_entity, user_entity.c.id == annotations.c.user_sub)\
        .where(annotations.c.annot_id == annot_id)
    result = await database.fetch_one(query)
    if result is not None:
        return Annotation(
                title=result.title,
                user_sub=result.user_sub,
                created_at=result.created_at,
                updated_at=result.updated_at,
                content=result.content,
                url=result.url,
                datasets=result.datasets,
                full_name=f'{result.first_name} {result.last_name}'
                if result.first_name is not None and result.last_name is not None
                else "Mitwelten User",
                username=result.username if result.username is not None else "mitwelten",
                id=result.annot_id
            )
    raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"There exists no annotation with id {annot_id}")

@router.delete('/explore/annotations/{annot_id}')
async def delete_annotation(annot_id: int, request: Request, is_allowed: bool = Depends(AuthenticationChecker())):
    auth_header = request.headers.get("authorization")
    if auth_header is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Authentication failed',
            headers={'WWW-Authenticate': 'Bearer'},
        )
    user = get_user(auth_header.split("Bearer ")[1])
    if 'explore_admin' not in user['realm_access']['roles']:
        user_sub = user.get("sub")
        if user_sub is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail='Authentication failed',
                headers={'WWW-Authenticate': 'Bearer'},
            )
        stmt = delete(annotations).where(
            and_(
                annotations.c.annot_id == annot_id,
                annotations.c.user_sub == user_sub
            )
        )
    else:
        stmt = delete(annotations).where(
                annotations.c.annot_id == annot_id
            )
    transaction = await database.transaction()
    try:
        await database.execute(stmt)

    except Exception as e:
        await transaction.rollback()
        print(str(e))
        raise HTTPException(status_code=409, detail=str(e))

    else:
        await transaction.commit()
        return True

@router.post('/explore/annotations')
async def post_annotation(body: AnnotationContent, request: Request, is_allowed: bool = Depends(AuthenticationChecker())):
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
        values = {
            annotations.c.title: body.title,
            annotations.c.user_sub: body.user_sub,
            annotations.c.created_at: body.created_at,
            annotations.c.updated_at: body.updated_at,
            annotations.c.content: body.content,
            annotations.c.url: body.url,
            annotations.c.datasets: body.datasets,
        }
        await database.execute(insert(annotations).values(values))

    except Exception as e:
        await transaction.rollback()
        print(str(e))
        raise HTTPException(status_code=409, detail=str(e))

    else:
        await transaction.commit()
        return True

@router.put('/explore/annotations/{annot_id}')
async def post_annotation(annot_id: int,body: AnnotationText, request: Request, is_allowed: bool = Depends(AuthenticationChecker())):
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
        stmt = update(annotations).where(and_(annotations.c.user_sub == user_sub, annotations.c.annot_id == annot_id)).values(content=body.content)
        await database.execute(stmt)

    except Exception as e:
        await transaction.rollback()
        print(str(e))
        raise HTTPException(status_code=409, detail=str(e))

    else:
        await transaction.commit()
        return True
