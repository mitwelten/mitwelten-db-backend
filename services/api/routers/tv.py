from typing import Optional
from hashlib import md5

from api.database import database
from api.dependencies import to_inclusive_range
from api.models import TimeStampRange

from fastapi import APIRouter, Request
from fastapi_cache.decorator import cache
from fastapi_cache import FastAPICache
from sqlalchemy.sql import text
from astral.sun import sun
from astral import LocationInfo

import credentials as crd

router = APIRouter(tags=['images', 'wildcam-tv'])

def is_day(time, observer):
    s = sun(observer, date=time.date())
    return time >= s['sunrise'] and time < s['sunset']

def request_key_builder(
    func,
    namespace: str = '',
    request: Request = None,
    *args,
    **kwargs,
):
    prefix = f'{FastAPICache.get_prefix()}:{namespace}:'
    cache_key = (
        prefix + md5(':'.join([
                request.method.lower(),
                request.url.path,
                repr(sorted(request.query_params.items()))
            ]).encode()
        ).hexdigest()
    )
    return cache_key


# @router.get('/tv/debug-cache/')
# async def get_debug_cache(key: str):
#     b = FastAPICache.get_backend()
#     return await b.get(key)

# @router.post('/tv/debug-cache/')
# async def post_debug_cache(body: dict):
#     b = FastAPICache.get_backend()
#     await b.set(body['key'], body['value'])

@router.get('/tv/stack-selection/')
@cache(expire=24*3600, key_builder=request_key_builder, namespace='wildcam-tv')
async def get_stack_selection(
    deployment_id: int,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
    phase: Optional[str] = None,
    interval: Optional[int] = None
):
    period = TimeStampRange.validate_type({'start': period_start, 'end': period_end})
    phase = phase if phase == 'night' or phase == 'day' else None

    query = text(f'''
    with file_ids as (
        select mfs.file_id as file_id, max(mfs.type) as type
        from {crd.db.schema}.mm_files_image_storage mfs
        left join {crd.db.schema}.storage_backend sb on mfs.storage_id = sb.storage_id
        left join {crd.db.schema}.files_image f on mfs.file_id = f.file_id
        where
            deployment_id = :deployment_id
            and sb.priority = 1
            and :period ::tstzrange @> time
        group by mfs.file_id, mfs.type, sb.storage_id
    )
    select
        case when file_ids.type = 1 then replace(object_name, '.jpg', '.webp') else object_name end,
        time
    from file_ids
    left join {crd.db.schema}.files_image f on file_ids.file_id = f.file_id
    order by time
    ''').bindparams(
        deployment_id=deployment_id,
        period=to_inclusive_range(period)
    )
    records = await database.fetch_all(query)
    if phase:
        result = await database.fetch_one(text(f'select location from {crd.db.schema}.deployments where deployment_id = :id').bindparams(id=deployment_id))
        coords = list(result['location'])
        location = LocationInfo(latitude=coords[0], longitude=coords[1])
        if phase == 'day':
            records = [dict(r) for r in records if is_day(r['time'], location.observer)]
        if phase == 'night':
            records = [dict(r) for r in records if not is_day(r['time'], location.observer)]

    if not interval:
        return records
    else:
        records = records
        interval = max(interval, 1)
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
