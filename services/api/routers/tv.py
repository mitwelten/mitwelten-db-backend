from api.database import database
from api.dependencies import to_inclusive_range
from api.models import TVStackSelectionRequest

from fastapi import APIRouter
from sqlalchemy.sql import text

import credentials as crd

router = APIRouter(tags=['images', 'wildcam-tv'])

@router.post('/tv/stack-selection/')
async def post_stack_selection(body: TVStackSelectionRequest):
    query = text(f'''
    select * from {crd.db.schema}.files_image
    where
        deployment_id = :deployment_id
        and :period ::tstzrange @> time
    order by time
    ''').bindparams(
        deployment_id=body.deployment_id,
        period=to_inclusive_range(body.period)
    )
    if not body.interval:
        return await database.fetch_all(query)
    else:
        records = await database.fetch_all(query)
        interval = max(body.interval, 1)
        filtered_records = []
        delta_sum = 0
        for i, r in enumerate(records):
            if i == 0:
                filtered_records.append(r)
                continue
            prev_time = records[i-1]['time']
            curr_time = r['time']
            delta_sum += (curr_time - prev_time).total_seconds()
            if delta_sum >= interval:
                filtered_records.append(r)
                delta_sum = 0
        return filtered_records
