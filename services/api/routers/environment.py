from api.database import database
from fastapi import APIRouter, Depends, Request, HTTPException, status
from api.dependencies import AuthenticationChecker
from sqlalchemy.sql import select, text
from api.tables import environment
from typing import List
from api.models import EnvironmentEntry, Point
import credentials as crd


router = APIRouter(tags=['environment'])

# ------------------------------------------------------------------------------
# Environment Characteristics
# ------------------------------------------------------------------------------

@router.get('/environment/entries',response_model=List[EnvironmentEntry])
async def get_environment_entries() -> List[EnvironmentEntry]:
    query = select(environment)
    return await database.fetch_all(query)

@router.get('/environment/nearest',response_model=List[EnvironmentEntry])
async def get_nearest_environment_entries(
    lat:float,
    lon:float,
    limit:int = 5,
    ) -> List[EnvironmentEntry]:
    query = text(f"""
        SELECT *,
        acos(
            sin(radians(location[0])) * sin(radians(:lat)) +  
            cos(radians(location[0])) * cos(radians(:lat)) *
            cos(radians(:lon ) - radians(location[1]))
            ) * 6371000 as distance
        FROM {crd.db.schema}.environment
        order by distance ASC
        LIMIT :limit
        """).bindparams(lat = lat, lon = lon, limit = limit)

    results = await database.fetch_all(query)
    return [
        EnvironmentEntry(
        environment_id = r.environment_id,
        location = Point(lat=r.location[0], lon=r.location[1]),
        timestamp = r.timestamp,
        attribute_01 = r.attribute_01,
        attribute_02 = r.attribute_02,
        attribute_03 = r.attribute_03,
        attribute_04 = r.attribute_04,
        attribute_05 = r.attribute_05,
        attribute_06 = r.attribute_06,
        attribute_07 = r.attribute_07,
        attribute_08 = r.attribute_08,
        attribute_09 = r.attribute_09,
        attribute_10 = r.attribute_10,
        created_at = r.created_at,
        updated_at = r.updated_at,
        distance = r.distance,
        ) 
        for r in results]

