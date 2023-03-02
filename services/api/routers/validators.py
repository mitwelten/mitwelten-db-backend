from api.config import crd
from api.database import database
from api.dependencies import to_inclusive_range
from api.models import DeploymentRequest, ValidationResult, NodeValidationRequest, Tag, ImageValidationResponse, ImageValidationRequest
from api.tables import deployments, nodes, tags

from asyncpg.exceptions import ExclusionViolationError
from fastapi import APIRouter
from sqlalchemy.sql import select, text

router = APIRouter()

# ------------------------------------------------------------------------------
# VALIDATORS
# ------------------------------------------------------------------------------

@router.put('/validate/deployment', response_model=ValidationResult, tags=['deployments'])
async def validate_deployment(body: DeploymentRequest) -> None:
    transaction = await database.transaction()
    try:

        values = {
            deployments.c.node_id: body.node_id,
            deployments.c.location: text('point(:lat,:lon)').bindparams(lat=body.location.lat,lon=body.location.lon),
            deployments.c.period: to_inclusive_range(body.period),
        }
        if hasattr(body, 'description') and body.description != None:
            values[deployments.c.description] = body.description

        if hasattr(body, 'deployment_id') and body.deployment_id != None:
            # this is an update
            # update the record to see if it conflicts
            await database.execute(deployments.update().\
                where(deployments.c.deployment_id == body.deployment_id).\
                values(values))
        else:
            # this is a new record, try to insert
            await database.execute(deployments.insert().\
                values(values))
    except ExclusionViolationError as e:
        await transaction.rollback()
        return True
    except Exception as e:
        await transaction.rollback()
        return True
    else:
        await transaction.rollback()
        return False

@router.put('/validate/node', response_model=ValidationResult, tags=['deployments'])
async def validate_node(body: NodeValidationRequest) -> ValidationResult:
    r = None
    if hasattr(body, 'node_id') and body.node_id != None:
        r = await database.fetch_one(select(nodes).\
            where(nodes.c.node_label == body.node_label, nodes.c.node_id != body.node_id))
    else:
        r = await database.fetch_one(select(nodes).where(nodes.c.node_label == body.node_label))
    return True if r == None else False

@router.put('/validate/tag', response_model=ValidationResult, tags=['deployments'])
async def validate_tag(body: Tag) -> ValidationResult:
    r = None
    if hasattr(body, 'tag_id') and body.tag_id != None:
        r = await database.fetch_one(select(tags).\
            where(tags.c.name == body.name, tags.c.tag_id != body.tag_id))
    else:
        r = await database.fetch_one(select(tags).where(tags.c.name == body.name))
    return True if r == None else False


@router.post('/validate/image', response_model=ImageValidationResponse, tags=['ingest'])
async def check_image(body: ImageValidationRequest) -> None:

    duplicate_query = text(f'''
    WITH n AS (
        SELECT :sha256 as sha256,
        :node_label ||'/'||to_char(:timestamp at time zone 'UTC', 'YYYY-mm-DD/HH24/') -- file_path (node_label, timestamp)
        || :node_label ||'_'||to_char(:timestamp at time zone 'UTC', 'YYYY-mm-DD"T"HH24-MI-SS"Z"')||:extension -- file_name (node_label, timestamp, extension)
        as object_name
    )
    SELECT f.sha256 = n.sha256 as hash_match,
        f.object_name = n.object_name as object_name_match,
        n.object_name as object_name
    from {crd.db.schema}.files_image f, n
    where (f.sha256 = n.sha256 or f.object_name = n.object_name)
    ''').bindparams(sha256=body.sha256, node_label=body.node_label, timestamp=body.timestamp, extension='.jpg')

    # print(str(query.compile(compile_kwargs={"literal_binds": True})))
    duplicate_result = await database.fetch_one(duplicate_query)

    object_name = None
    if duplicate_result == None:
        object_name_query = text('''
        SELECT :node_label ||'/'||to_char(:timestamp at time zone 'UTC', 'YYYY-mm-DD/HH24/') -- file_path (node_label, timestamp)
        || :node_label ||'_'||to_char(:timestamp at time zone 'UTC', 'YYYY-mm-DD"T"HH24-MI-SS"Z"')||:extension -- file_name (node_label, timestamp, extension)
        as object_name
        ''').bindparams(node_label=body.node_label, timestamp=body.timestamp, extension='.jpg')
        object_name_result = await database.fetch_one(object_name_query)
        object_name = object_name_result._mapping['object_name']
    else:
        object_name = duplicate_result._mapping['object_name']

    deployment_query = select(deployments.c.deployment_id).join(nodes).\
        where(nodes.c.node_label == body.node_label, text('period @> :timestamp ::timestamptz').bindparams(timestamp=body.timestamp))
    deployment_result = await database.fetch_one(deployment_query)

    if duplicate_result == None:
        if deployment_result:
            return { # no duplicate, deployed: validation passed
                'hash_match': False, 'object_name_match': False, 'object_name': object_name,
                **deployment_result._mapping, 'node_deployed': True }
        else:
            return { # no duplicate, NOT deployed: validation failed
                'hash_match': False, 'object_name_match': False, 'object_name': object_name,
                'deployment_id': None, 'node_deployed': False }
    else:
        if deployment_result:
            return { # DUPLICATE, deployed: validation failed
                **duplicate_result._mapping,
                **deployment_result._mapping, 'node_deployed': True }
        else:
            return { # DUPLICATE, NOT deployed: validation failed
                **duplicate_result._mapping,
                'deployment_id': None, 'node_deployed': False }
