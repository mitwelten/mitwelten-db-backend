from typing import Optional, List, Tuple, Literal
from enum import Enum
from datetime import datetime
from sqlalchemy.dialects.postgresql import TSTZRANGE
from pydantic import BaseModel, Field, constr, PositiveInt
from asyncpg.types import Range

class TimeStampRange(BaseModel):
    '''
## Field mapping from/to TSTZRANGE

__Time range defined as two timestamps with time zone__

When inserting/updating, provide the range as an object with the keys
`start` and `end` holding the corresponding timestamp. The timestamps can be
in the format `2021-09-11T22:00:00+00:00` or `2021-09-11T22:00:00Z`, in the
latter case the `Z` is replaced by `+00:00` to make it compatible to pythons
`datetime.fromisoformat()`.

```json
{
    "start": "2021-09-11T22:00:00+00:00",
    "end": "2021-10-14T22:00:00+00:00"
}
```

This object will be turned into the postgres type `tstzrange` like this (note
the interval definition "including start timestamp up until, but not including
end timestamp):

```sql
['2021-09-12 00:00:00+02:00','2021-10-15 00:00:00+02:00')
```

The pydantic model / type definition also converts this `tstzrange` back into
the aforementioned format when retrieving (using as a response model).
'''
    start: datetime = Field(..., example='2021-09-11T22:00:00+00:00', title="Beginning of period (inclusive)")
    end: datetime = Field(..., example='2021-10-14T22:00:00Z', title="End of period (non inclusive)")

    def __init__(self, start: datetime, end: datetime):
        self.start = start
        self.end = end

    def stripz(ts):
        assert isinstance(ts, str)
        return ts[0:len(ts)-1]+'+00:00' if ts[-1] == 'Z' else ts

    @classmethod
    def __get_validators__(cls):
        yield cls.validate_type

    @classmethod
    def validate_type(cls, val: Range):
        if isinstance(val, Range):
            return {'start': val.lower, 'end': val.upper}
        elif 'start' in val and 'end' in val:
            lower = None
            upper = None
            if val['start'] != '' and val['start'] != None:
                lower = datetime.fromisoformat(cls.stripz(val['start']))
            if val['end'] != '' and val['end'] != None:
                upper = datetime.fromisoformat(cls.stripz(val['end']))
            return Range(lower=lower, upper=upper)

    def __repr__(self):
        return f'TimeStampRange({super().__repr__()})'

class ValidationResult(BaseModel):
    __root__: bool

class NodeValidationRequest(BaseModel):
    node_id: Optional[int]
    node_label: str

class ImageValidationRequest(BaseModel):
    sha256: str
    node_label: str
    timestamp: datetime

    class Config:
        json_encoders = {
            datetime: lambda v: v.timestamp(),
        }

class ImageValidationResponse(BaseModel):
    hash_match: bool
    object_name_match: bool
    object_name: str
    node_deployed: bool
    deployment_id: Optional[int] = None


class ImageRequest(BaseModel):
    object_name: str
    sha256: str
    timestamp: datetime
    deployment_id: int
    file_size: int
    resolution: Tuple[PositiveInt, PositiveInt]

    class Config:
        json_encoders = {
            datetime: lambda v: v.timestamp(),
        }

class Result(BaseModel):
    result_id: int
    file_id: int
    time_start: float
    time_end: float
    confidence: float
    species: str

class Species(BaseModel):
    species: str
    confidence: float
    time_start: datetime

class Point(BaseModel):
    '''
    Coordinate in WGS84 format
    '''
    lat: float = Field(..., example=47.53484943172696, title="Latitude (WGS84)")
    lon: float = Field(..., example=7.612519197679952, title="Longitude (WGS84)")

class ResultFull(Species):
    location: Point
    object_name: str
    object_time: datetime
    time_start_relative: float
    duration: float
    image_url: Optional[str]
    species_de: Optional[str] = None
    species_en: Optional[str] = None
    genus: Optional[str] = None
    family: Optional[str] = None
    _class: Optional[str] = Field(None, alias='class')
    phylum: Optional[str] = None
    kingdom: str

class ResultsGrouped(BaseModel):
    species: str
    time_start_relative: float
    duration: float
    image_url: Optional[str]

class RankEnum(str, Enum):
    kingdom = 'KINGDOM'
    phylum = 'PHYLUM'
    _class = 'CLASS'
    family = 'FAMILY'
    genus = 'GENUS'
    species = 'SPECIES'
    subspecies = 'SUBSPECIES'

class Taxon(BaseModel):
    datum_id: int
    label_sci: str
    label_de: Optional[str]
    label_en: Optional[str]
    image_url: Optional[str]
    rank: RankEnum

class Tag(BaseModel):
    '''
    Annotation
    '''

    tag_id: int
    name: constr(regex=r'\w+')

class TagStats(Tag):
    '''
    Annotation with assignment count
    '''

    deployments: int
    entries: int
    created_at: datetime
    updated_at: datetime

class Node(BaseModel):
    '''
    A device deployed in the field, commondly collecting and/or processing data
    '''
    node_id: Optional[int] = None
    node_label: constr(regex=r'\d{4}-\d{4}')
    type: str
    serial_number: Optional[str]
    description: Optional[str]
    platform: Optional[str]
    connectivity: Optional[str]
    power: Optional[str]
    hardware_version: Optional[str]
    software_version: Optional[str]
    firmware_version: Optional[str]

class Deployment(BaseModel):
    '''
    Deployment
    '''

    deployment_id: Optional[int] = None
    node_id: int
    location: Point
    description: Optional[str] = None
    period: TimeStampRange
    tags: Optional[List[Tag]] = None

class DeploymentResponse(Deployment):
    '''
    DeploymentResponse: Deploymnet including associated node record
    '''

    node: Node
    tags: Optional[List[Tag]] = None

class DeploymentRequest(BaseModel):
    '''
    Deployment
    '''

    deployment_id: Optional[int] = None
    node_id: int
    location: Point
    description: Optional[str] = None
    period: TimeStampRange
    tags: Optional[List[str]] = None

class QueueInputDefinition(BaseModel):
    node_label: str # for now keep this required. TODO: implement update for all dask when node_label not present

class QueueUpdateDefinition(BaseModel):
    node_label: str # for now keep this required. TODO: implement update for all dask when node_label not present
    action: Literal['reset_all', 'reset_failed', 'pause', 'resume']
