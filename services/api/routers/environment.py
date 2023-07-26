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

# TODO: Add table to database
@router.get('/environment/legend')
def get_environment_legend():
    legend = {
        "attribute_01": {
            "label": "Siedlungsfaktor",
            "description": [
            "Offene Landschaft",
            "Gemäßigte Besiedlung",
            "Stark besiedeltes Gebiet"
            ]
        },
        "attribute_02": {
            "label": "Bodenversiegelung",
            "description": [
            "Keine Versiegelung",
            "Teilweise versiegelter Boden",
            "Vollständig versiegelter Boden",
            ]
        },
        "attribute_03": {
            "label": "Sonneneinstrahlung",
            "description": [
            "Keine direkte Sonneneinstrahlung",
            "Mäßige Sonneneinstrahlung",
            "Kontinuierliche Sonneneinstrahlung",
            ]
        },
        "attribute_04": {
            "label": "Gewässer",
            "description": [
            "Keine Gewässer in der Nähe",
            "Nahegelegenes Gewässer",
            "Direkt am Gewässer",
            ]
        },
        "attribute_05": {
            "label": "Blühangebot",
            "description": [
            "Geringes Blühangebot",
            "Mäßiges Blühangebot",
            "Sehr hohes Blühangebot",
            ]
        },
        "attribute_06": {
            "label": "Substratvorkommen",
            "description": [
            "Kein Vorkommen von organischem Substrat",
            "Mäßiges Vorkommen von organischem Substrat",
            "Sehr hohes Vorkommen von organischem Substrat",
            ]
        },
        "attribute_07": {
            "label": "Nistmöglichkeit",
            "description": [
            "Sehr ungeeignet für Bestäubernester",
            "Mäßig geeignet für Bestäubernester",
            "Sehr geeignet für Bestäubernester",
            ]
        },
        "attribute_08": {
            "label": "Fragmentierung",
            "description": [
            "Geringe Fragmentierung der Landschaft",
            "Mäßige Fragmentierung der Landschaft",
            "Hohe Fragmentierung der Landschaft",
            ]
        },
        "attribute_09": {
            "label": "Habitatvielfalt",
            "description": [
            "Geringe Vielfalt natürlicher Lebensräume",
            "Mäßige Vielfalt natürlicher Lebensräume",
            "Hohe Vielfalt natürlicher Lebensräume",
            ]
        },
        "attribute_10": {
            "label": "Pflanzenvielfalt",
            "description": [
            "Geringe Pflanzenvielfalt",
            "Mäßige Pflanzenvielfalt",
            "Hohe Pflanzenvielfalt",
            ]
        }
    }
    return legend

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

@router.get('/environment/attribute/{attribute_id}')
async def get_environment_data(attribute_id:str):
    valid_attribute_ids = [
        'attribute_01', 'attribute_02', 'attribute_03', 'attribute_04', 'attribute_05',
        'attribute_06', 'attribute_07', 'attribute_08', 'attribute_09', 'attribute_10'
    ]
    if attribute_id not in valid_attribute_ids:
        raise HTTPException(status_code=400,detail={'error': 'Invalid attribute_id'})
    column = getattr(environment.c, attribute_id).label("value")
    query = select(environment.c.environment_id,
                   environment.c.location,
                   environment.c.timestamp,
                   column)
    return await database.fetch_all(query)
