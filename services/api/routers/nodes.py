from typing import List, Optional
from datetime import datetime

from api.database import database
from api.dependencies import check_authentication
from api.models import Node, DeployedNode
from api.tables import deployments, nodes

from asyncpg.exceptions import ForeignKeyViolationError
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.sql import delete, insert, distinct, select, func, update, text, LABEL_STYLE_TABLENAME_PLUS_COL
from sqlalchemy.sql.functions import current_timestamp

router = APIRouter(tags=['nodes'])

# ------------------------------------------------------------------------------
# NODES
# ------------------------------------------------------------------------------

@router.get('/nodes')
async def read_nodes():
    deployments_subquery = select(func.count(deployments.c.deployment_id)).\
        where(nodes.c.node_id == deployments.c.node_id).scalar_subquery()
    return await database.fetch_all(select(nodes, deployments_subquery.label('deployment_count')).\
        order_by(nodes.c.node_label))

@router.put('/nodes', dependencies=[Depends(check_authentication)])
async def upsert_node(body: Node) -> None:
    if hasattr(body, 'node_id') and body.node_id != None:
        return await database.execute(update(nodes).where(nodes.c.node_id == body.node_id).\
            values({**body.dict(exclude_none=True), nodes.c.updated_at: current_timestamp()}).\
            returning(nodes.c.node_id))
    else:
        return await database.execute(insert(nodes).values(body.dict(exclude_none=True)).\
            returning(nodes.c.node_id))

@router.get('/node/type_options')
@router.get('/node/type_options/{search_term}')
async def get_node_type(search_term: Optional[str] = None) -> List[str]:
    q = select(distinct(nodes.c.type))
    if search_term != None:
        q = q.where(nodes.c.type.ilike(f'{search_term}%'))
    r = await database.fetch_all(q.order_by(nodes.c.type))
    return [v[nodes.c.type] for v in r if v[nodes.c.type] != None]

@router.get('/node/platform_options')
@router.get('/node/platform_options/{search_term}')
async def get_node_platform(search_term: Optional[str] = None) -> List[str]:
    q = select(distinct(nodes.c.platform))
    if search_term != None:
        q = q.where(nodes.c.platform.ilike(f'{search_term}%'))
    r = await database.fetch_all(q.order_by(nodes.c.platform))
    return [v[nodes.c.platform] for v in r if v[nodes.c.platform] != None]

@router.get('/node/connectivity_options')
@router.get('/node/connectivity_options/{search_term}')
async def get_node_connectivity(search_term: Optional[str] = None) -> List[str]:
    q = select(distinct(nodes.c.connectivity))
    if search_term != None:
        q = q.where(nodes.c.connectivity.ilike(f'{search_term}%'))
    r = await database.fetch_all(q.order_by(nodes.c.connectivity))
    return [v[nodes.c.connectivity] for v in r if v[nodes.c.connectivity] != None]

@router.get('/node/power_options')
@router.get('/node/power_options/{search_term}')
async def get_node_power(search_term: Optional[str] = None) -> List[str]:
    q = select(distinct(nodes.c.power))
    if search_term != None:
        q = q.where(nodes.c.power.ilike(f'{search_term}%'))
    r = await database.fetch_all(q.order_by(nodes.c.power))
    return [v[nodes.c.power] for v in r if v[nodes.c.power] != None]

@router.get('/node', response_model=Node)
async def read_node_by_label(label: str) -> Node:
    return await database.fetch_one(select(nodes).where(nodes.c.node_label == label))

@router.get('/node/{id}', response_model=Node)
async def read_node(id: int) -> Node:
    return await database.fetch_one(select(nodes).where(nodes.c.node_id == id))

@router.delete('/node/{id}', response_model=None, dependencies=[Depends(check_authentication)])
async def delete_node(id: int) -> None:
    try:
        await database.fetch_one(delete(nodes).where(nodes.c.node_id == id))
    except ForeignKeyViolationError as e:
        raise HTTPException(status_code=409, detail=str(e))
    else:
        return True

# ----------------------------

@router.get('/viz/nodes', response_model=List[DeployedNode], tags=['deployments', 'viz'],
    summary='Deployed nodes for viz dashboard')
async def list_viz_nodes(
    time_from: Optional[datetime] = Query(None, alias='from', example='2021-09-01T00:00:00.000Z'),
    time_to: Optional[datetime] = Query(None, alias='to', example='2022-08-31T23:59:59.999Z'),
) -> List[DeployedNode]:
    '''
    List all deployed nodes
    '''

    query = select(deployments.alias('d').outerjoin(nodes.alias('n'))).\
        set_label_style(LABEL_STYLE_TABLENAME_PLUS_COL)

    # define time range criteria
    if time_from and time_to:
        query = query.where(text("n.type != 'Test'"), text("d.period && tstzrange(:time_from, :time_to)").bindparams(time_from=time_from, time_to=time_to))
    elif time_from:
        query = query.where(text("n.type != 'Test'"), text("d.period && tstzrange(:time_from, 'infinity')").bindparams(time_from=time_from))
    elif time_to:
        query = query.where(text("n.type != 'Test'"), text("d.period && tstzrange('-infinity', :time_to)").bindparams(time_to=time_to))
    else:
        query = query.where(text("n.type != 'Test'"))

    result = await database.fetch_all(query)
    return [{
        'id': r['n_node_id'],
        'name': r['n_node_label'],
        'location': r['d_location'],
        'location_description': r['d_description'],
        'type': r['n_type'],
        'platform': r['n_platform'],
        'description': r['n_description'],
    } for r in result]
