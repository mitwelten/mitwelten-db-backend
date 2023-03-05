from itertools import filterfalse, groupby
from typing import List, Optional

from api.database import database
from api.dependencies import check_oid_authentication, from_inclusive_range, to_inclusive_range, unique_everseen
from api.exceptions import RecordsDependencyException
from api.models import DeploymentRequest, DeploymentResponse
from api.tables import data_records, deployments, mm_tags_deployments, nodes, tags

from asyncpg.exceptions import ExclusionViolationError
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import LABEL_STYLE_TABLENAME_PLUS_COL
from sqlalchemy.sql import and_, delete, exists, not_, or_, select, text

router = APIRouter(tags=['deployments'])

# ------------------------------------------------------------------------------
# DEPLOYMENTS
# ------------------------------------------------------------------------------

@router.get('/deployments', response_model=List[DeploymentResponse])
async def read_deployments(node_id: Optional[int] = None) -> List[DeploymentResponse]:

    query = select(deployments.alias('d').outerjoin(nodes.alias('n')).\
        outerjoin(mm_tags_deployments.alias('mm')).outerjoin(tags.alias('t'))).\
        set_label_style(LABEL_STYLE_TABLENAME_PLUS_COL)
    if node_id != None:
        query = query.where(text('d.node_id = :node_id').bindparams(node_id=node_id))
    result = await database.fetch_all(query)
    response = []
    for key, grp in groupby(result, key=lambda x: x['d_deployment_id']):
        grp = list(grp)
        t_l = unique_everseen(grp, lambda x: x['t_tag_id'])
        r = dict(grp[0])
        d = { c: r['d_'+c] for c in deployments.columns.keys() }
        d['node'] = { c: r['n_'+c] for c in nodes.columns.keys() }
        d['period'] = from_inclusive_range(d['period'])
        d['tags'] = [{'tag_id': t['t_tag_id'], 'name': t['t_name']} for t in t_l if t['t_tag_id'] != None]
        response.append(d)
    return response

@router.get('/deployment/{id}', response_model=DeploymentResponse)
async def read_deployment(id: int) -> DeploymentResponse:

    query = select(deployments.alias('d').outerjoin(nodes.alias('n')).\
        outerjoin(mm_tags_deployments.alias('mm')).outerjoin(tags.alias('t'))).\
        where(text('deployment_id = :id').bindparams(id=id)).set_label_style(LABEL_STYLE_TABLENAME_PLUS_COL)

    r = await database.fetch_all(query)
    if r == None:
        raise HTTPException(status_code=404, detail='Deployment not found')

    t_l = unique_everseen(r, lambda x: x['t_tag_id'])
    d = { c: r[0]['d_'+c] for c in deployments.columns.keys() }
    d['node'] = { c: r[0]['n_'+c] for c in nodes.columns.keys() }
    d['period'] = from_inclusive_range(d['period'])
    d['tags'] = [{'tag_id': t['t_tag_id'], 'name': t['t_name']} for t in t_l if t['t_tag_id'] != None]
    return d

@router.delete('/deployment/{id}', response_model=None, dependencies=[Depends(check_oid_authentication)])
async def delete_deployment(id: int) -> None:
    transaction = await database.transaction()
    try:
        # asyncpg doesn't support returning affected rowcount yet (https://github.com/encode/databases/issues/61)
        # checking the constraint manually
        exists_files_audio = (exists().where(data_records.c.deployment_id == deployments.c.deployment_id))
        q = select(deployments).where(deployments.c.deployment_id == id, not_(exists_files_audio))
        r = await database.fetch_one(q)
        if r == None:
            raise RecordsDependencyException('There are data records referring to the node in the deployment do be deleted.')
        await database.execute(delete(deployments).where(deployments.c.deployment_id == id, not_(exists_files_audio)))
    except RecordsDependencyException as e:
        await transaction.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        await transaction.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    else:
        await transaction.commit()
        return True

@router.post('/deployments', response_model=None, dependencies=[Depends(check_oid_authentication)])
@router.put('/deployments', response_model=None, dependencies=[Depends(check_oid_authentication)])
async def upsert_deployment(body: DeploymentRequest) -> None:
    '''
    Insert or update a deployment
    '''

    try:
        values = {
            deployments.c.node_id: body.node_id,
            deployments.c.location: text('point(:lat,:lon)').\
                bindparams(lat=body.location.lat,lon=body.location.lon),
            deployments.c.period: to_inclusive_range(body.period),
        }
        if hasattr(body, 'description') and body.description != None:
            values[deployments.c.description] = body.description

        transaction = await database.transaction()
        if hasattr(body, 'deployment_id') and body.deployment_id != None:
            # this is an update
            # update the record to see if it conflicts
            await database.execute(deployments.update().\
                where(deployments.c.deployment_id == body.deployment_id).\
                values(values))

            # deal with tags
            if hasattr(body, 'tags') and body.tags != None and isinstance(body.tags, list):
                tu = set(body.tags) # tags, unique
                # select from tags where name in list from request or assoc with deployment_id
                r = await database.fetch_all(select(tags.c.tag_id, tags.c.name, mm_tags_deployments.c.deployments_deployment_id.label('deployment_id')).\
                    outerjoin(mm_tags_deployments, mm_tags_deployments.c.tags_tag_id == tags.c.tag_id).\
                    where(or_(tags.c.name.in_(tu), mm_tags_deployments.c.deployments_deployment_id == body.deployment_id)))

                # split tags in already assoc and unassoc
                pred = lambda x: x['deployment_id'] != body.deployment_id

                at = list(filterfalse(pred, r))                           # Associated Tags: don't do anything with those, used for delete filter
                ut = [t for t in filter(pred, r) if t['tag_id'] not in [a['tag_id'] for a in at]] # Unassociated Tags: assoc these
                nt = [t for t in tu if t not in [rt['name'] for rt in r]] # New Tags: add these and assoc
                dt = [t for t in at if t['name'] not in tu]               # Delete Tags: delete these from nm table

                # deassoc Delete Tags (previously associated)
                if len(dt):
                    await database.execute(mm_tags_deployments.delete().where(and_(
                        mm_tags_deployments.c.tags_tag_id.in_([t['tag_id'] for t in dt]),
                        mm_tags_deployments.c.deployments_deployment_id == body.deployment_id)))

                # insert New Tags
                unt = []
                if len(nt):
                    nti = await database.fetch_all(tags.insert().values([{'name': n} for n in nt]).\
                        returning(tags.c.tag_id, tags.c.name))
                    # combine existing (u) with new (n) tags
                    if len(nti): unt.extend([x['tag_id'] for x in nti])

                # insert join records
                if len(ut): unt.extend(set([x['tag_id'] for x in ut]))
                if len(unt):
                    await database.fetch_all(mm_tags_deployments.insert().values(
                        [{'tags_tag_id': t, 'deployments_deployment_id': body.deployment_id} for t in set(unt)]))
            await transaction.commit()

        else:
            # this is a new record, try to insert
            d = await database.fetch_one(deployments.insert().\
                values(values))

            # deal with tags
            if hasattr(body, 'tags') and body.tags != None and isinstance(body.tags, list):
                tu = set(body.tags) # tags, unique
                # select from tags where name in list from request
                r = await database.fetch_all(select(tags.c.tag_id, tags.c.name).\
                    where(tags.c.name.in_(tu)))
                # find the ones that don't exist
                nt = [t for t in tu if t not in [rt['name'] for rt in r]]
                # insert those and collect the returned ids
                ant = [x['tag_id'] for x in r]
                if len(nt):
                    nti = await database.fetch_all(tags.insert().values([{'name': n} for n in nt]).\
                        returning(tags.c.tag_id, tags.c.name))
                    # combine existing with new ones
                    ant.extend([x['tag_id'] for x in nti])
                # insert join records
                if len(ant):
                    await database.fetch_all(mm_tags_deployments.insert().values(
                        [{'tags_tag_id': t, 'deployments_deployment_id': d['deployment_id']} for t in ant]))
            await transaction.commit()

    except ExclusionViolationError as e:
        await transaction.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await transaction.rollback()
        raise HTTPException(status_code=500, detail=str(e))
