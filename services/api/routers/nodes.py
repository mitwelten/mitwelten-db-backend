from typing import List, Optional

from api.database import database
from api.dependencies import check_authentication
from api.models import Node
from api.tables import deployments, nodes

from asyncpg.exceptions import ForeignKeyViolationError
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.sql import delete, insert, distinct, select, func, update
from sqlalchemy.sql.functions import current_timestamp

router = APIRouter()

# ------------------------------------------------------------------------------
# NODES
# ------------------------------------------------------------------------------

@router.get('/nodes', tags=['deployments'])
async def read_nodes():
    deployments_subquery = select(func.count(deployments.c.deployment_id)).\
        where(nodes.c.node_id == deployments.c.node_id).scalar_subquery()
    return await database.fetch_all(select(nodes, deployments_subquery.label('deployment_count')).\
        order_by(nodes.c.node_label))

@router.put('/nodes', dependencies=[Depends(check_authentication)], tags=['deployments'])
async def upsert_node(body: Node) -> None:
    if hasattr(body, 'node_id') and body.node_id != None:
        return await database.execute(update(nodes).where(nodes.c.node_id == body.node_id).\
            values({**body.dict(exclude_none=True), nodes.c.updated_at: current_timestamp()}).\
            returning(nodes.c.node_id))
    else:
        return await database.execute(insert(nodes).values(body.dict(exclude_none=True)).\
            returning(nodes.c.node_id))

@router.get('/node/type_options', tags=['deployments'])
@router.get('/node/type_options/{search_term}', tags=['deployments'])
async def get_node_type(search_term: Optional[str] = None) -> List[str]:
    q = select(distinct(nodes.c.type))
    if search_term != None:
        q = q.where(nodes.c.type.ilike(f'{search_term}%'))
    r = await database.fetch_all(q.order_by(nodes.c.type))
    return [v[nodes.c.type] for v in r if v[nodes.c.type] != None]

@router.get('/node/platform_options', tags=['deployments'])
@router.get('/node/platform_options/{search_term}', tags=['deployments'])
async def get_node_platform(search_term: Optional[str] = None) -> List[str]:
    q = select(distinct(nodes.c.platform))
    if search_term != None:
        q = q.where(nodes.c.platform.ilike(f'{search_term}%'))
    r = await database.fetch_all(q.order_by(nodes.c.platform))
    return [v[nodes.c.platform] for v in r if v[nodes.c.platform] != None]

@router.get('/node/connectivity_options', tags=['deployments'])
@router.get('/node/connectivity_options/{search_term}', tags=['deployments'])
async def get_node_connectivity(search_term: Optional[str] = None) -> List[str]:
    q = select(distinct(nodes.c.connectivity))
    if search_term != None:
        q = q.where(nodes.c.connectivity.ilike(f'{search_term}%'))
    r = await database.fetch_all(q.order_by(nodes.c.connectivity))
    return [v[nodes.c.connectivity] for v in r if v[nodes.c.connectivity] != None]

@router.get('/node/power_options', tags=['deployments'])
@router.get('/node/power_options/{search_term}', tags=['deployments'])
async def get_node_power(search_term: Optional[str] = None) -> List[str]:
    q = select(distinct(nodes.c.power))
    if search_term != None:
        q = q.where(nodes.c.power.ilike(f'{search_term}%'))
    r = await database.fetch_all(q.order_by(nodes.c.power))
    return [v[nodes.c.power] for v in r if v[nodes.c.power] != None]

@router.get('/node', response_model=Node, tags=['deployments'])
async def read_node_by_label(label: str) -> Node:
    return await database.fetch_one(select(nodes).where(nodes.c.node_label == label))

@router.get('/node/{id}', response_model=Node, tags=['deployments'])
async def read_node(id: int) -> Node:
    return await database.fetch_one(select(nodes).where(nodes.c.node_id == id))

@router.delete('/node/{id}', response_model=None, dependencies=[Depends(check_authentication)], tags=['deployments'])
async def delete_node(id: int) -> None:
    try:
        await database.fetch_one(delete(nodes).where(nodes.c.node_id == id))
    except ForeignKeyViolationError as e:
        raise HTTPException(status_code=409, detail=str(e))
    else:
        return True
