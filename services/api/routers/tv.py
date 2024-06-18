from datetime import timedelta

from api.database import database
from api.dependencies import to_inclusive_range
from api.models import TimeStampRange, TVStackSelectionRequest
from api.tables import files_image

from fastapi import APIRouter
from sqlalchemy.sql import select, text

import credentials as crd


router = APIRouter(tags=['images', 'walk'])

async def post_stack_selection(body: dict):
    print(body)
    images = select(files_image).\
        where(files_image.c.deployment_id == 824).\
        order_by(files_image.c.time).limit(1000).offset(0);
        # where(files_image.c.file_size < 1000000).\
    return await database.fetch_all(images)

@router.post('/tv/stack-selection/')
async def post_imagestack(body: TVStackSelectionRequest):
    if not body.interval:
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
    else:
        query = text(f'''
        with
            time_delta as (
                select
                    object_name,
                    time,
                    coalesce(time - lag(time) over (order by time), '0 seconds') as delta
                from {crd.db.schema}.files_image
                where
                    deployment_id = :deployment_id
                    and :period ::tstzrange @> time
            ),
            sum_group as (
                select
                    *,
                    sum(case when dsum + delta > :interval then 1 else 0 end) over (order by time) as grp
                from (
                    select
                        *,
                        sum(delta) over (order by time) as dsum
                    from time_delta
                ) as delta_sums
            ),
            running_sum as (
                select
                    *,
                    sum(delta) over (partition by grp order by time) as rsum
                from sum_group
            )
        select *
        from running_sum
        where rsum > :interval
        ''').bindparams(
            interval=timedelta(seconds=body.interval),
            deployment_id=body.deployment_id,
            period=body.period
        )
    return await database.fetch_all(query)
