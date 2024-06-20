from api.database import database
from api.dependencies import to_inclusive_range
from api.models import TVStackSelectionRequest

from fastapi import APIRouter
from sqlalchemy.sql import text
from astral.sun import sun
from astral import LocationInfo

import credentials as crd

router = APIRouter(tags=['images', 'wildcam-tv'])

def is_day(time, observer):
    s = sun(observer, date=time.date())
    return time >= s['sunrise'] and time < s['sunset']

@router.post('/tv/stack-selection/')
async def post_stack_selection(body: TVStackSelectionRequest):
    query = text(f'''
    select object_name, time from {crd.db.schema}.files_image
    where
        deployment_id = :deployment_id
        and :period ::tstzrange @> time
    order by time
    ''').bindparams(
        deployment_id=body.deployment_id,
        period=to_inclusive_range(body.period)
    )
    records = await database.fetch_all(query)
    if body.phase:
        result = await database.fetch_one(text(f'select location from {crd.db.schema}.deployments where deployment_id = :id').bindparams(id=body.deployment_id))
        coords = list(result['location'])
        location = LocationInfo(latitude=coords[0], longitude=coords[1])
        if body.phase == 'day':
            records = [dict(r) for r in records if is_day(r['time'], location.observer)]
        if body.phase == 'night':
            records = [dict(r) for r in records if not is_day(r['time'], location.observer)]

    if not body.interval:
        return records
    else:
        records = records
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
