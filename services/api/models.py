from datetime import datetime
from enum import Enum
from typing import List, Literal, Optional, Tuple, Union

from api.config import s3_file_url_regex

from asyncpg.types import Range
from pydantic import BaseModel, Field, PositiveInt, constr
from sqlalchemy.dialects.postgresql import TSTZRANGE


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
    order = 'ORDER'
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
    node_label: constr(regex=r'\d{4}-\d{4}') = Field(
        ...,
        example='2323-4242',
        description='Identifyer, a.k.a _Node ID_, _Node Label_, or _Label_'
    )
    node_type: str = Field(..., example='Audio', description='Desription of function', alias='type')
    serial_number: Optional[str]
    description: Optional[str] = Field(
        None,
        example='Environmental sensor to record humidity, temperature and athmospheric pressure',
    )
    platform: Optional[str] = Field(None, example='Audiomoth', description='Hardware platform')
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

class DeployedNode(Node):
    '''
    Deployed Node for display in viz dashboard

    This is a compatibility type: Nodes don't have a location,
    but their associated deployment record does. This type is only used for the
    purpose of displaying deployed nodes in the viz dashboard.
    '''

    node_id: Optional[int] = Field(alias='id')
    node_label: constr(regex=r'\d{4}-\d{4}') = Field(..., alias='name')
    location: Point
    location_description: Optional[str] = None

class DeploymentResponse(Deployment):
    '''
    DeploymentResponse: Deployment including associated node record
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

class File(BaseModel):
    '''
    File uploaded through front end to S3, associated to an entry
    '''
    id: Optional[int] = None
    type: str = Field(title='MIME type', example='application/pdf')
    name: str = Field(title='File name')
    link: constr(strip_whitespace=True, regex=s3_file_url_regex) = Field(
        title='Link to S3 object',
        description='Constrained to project specific S3 bucket'
    )

class Comment(BaseModel):
    '''
    User-created comment in form of a __marker__ or __range label__
    '''
    id: Optional[int] = None
    comment: str = Field(..., example='We have observed this as well.')
    timeStart: datetime = Field(
        ...,
        example='2022-03-06T12:23:42.777Z',
        description='Point in time the comment is referring to. If `timeEnd` is given, `timeStart` indicates the beginning of a range.'
    )
    timeEnd: Optional[datetime] = Field(None, example='2022-03-06T12:42:23.777Z', description='End of the time range the comment is referring to')
    author: Optional[str] = None

class EnvTypeEnum(str, Enum):
    temperature = "temperature"
    humidity = "humidity"
    moisture = "moisture"

class EnvDatum(BaseModel):
    '''
    Datum of a measurement by an environmental sensor
    '''
    type: Literal['env', 'HumiTemp', 'HumiTempMoisture', 'Moisture']
    time: Optional[datetime] = None
    nodeLabel: Optional[constr(regex=r'\d{4}-\d{4}')] = None
    voltage: Optional[float] = Field(None, example=4.8)
    voltageUnit: Optional[str] = Field(None, example='V')
    temperature: Optional[float] = Field(None, example=7.82)
    temperatureUnit: Optional[str] = Field('°C', example='°C')
    humidity: Optional[float] = Field(None, example=93.78)
    humidityUnit: Optional[str] = Field('%', example='%')
    moisture: Optional[float] = Field(None, example=2.6)
    moistureUnit: Optional[str] = Field('g/m³', example='g/m³')

class PaxDatum(BaseModel):
    '''
    Datum of a measurement by a PAX sensor
    '''
    type: Literal['pax', 'Pax']
    time: Optional[datetime] = None
    nodeLabel: Optional[constr(regex=r'\d{4}-\d{4}')] = None
    voltage: Optional[float] = Field(None, example=4.8)
    voltageUnit: Optional[str] = Field('V', example='V')
    pax: Optional[int] = Field(None, example=17)
    paxUnit: Optional[str] = Field(None, example='')

class Datum(BaseModel):
    __root__: Union[EnvDatum, PaxDatum]

class DatumResponse(BaseModel):
    '''
    Response containing one of a selection of sensor data types
    '''
    __root__: Union[List[PaxDatum], List[EnvDatum]] = Field(..., discriminator='type')

class PaxMeasurement(BaseModel):
    time: datetime
    nodeLabel: Optional[constr(regex=r'\d{4}-\d{4}')] = None
    deviceEui: Optional[str] = None
    pax: int
    voltage: float

class ApiResponse(BaseModel):
    code: Optional[int] = None
    type: Optional[str] = None
    message: Optional[str] = None

class ApiErrorResponse(BaseModel):
    detail: Optional[str] = None

class EntryIdFilePostRequest(BaseModel):
    additionalMetadata: Optional[str] = Field(
        None, description='Additional data to pass to server'
    )
    file: Optional[bytes] = Field(None, description='File to upload')

class Entry(BaseModel):
    '''
    A user generated "pin" on the map to which `files`, `tags` and `comments` can be associated
    '''
    entry_id: Optional[int] = None
    date: Optional[datetime] = Field(None, example='2022-12-31T23:59:59.999Z', description='Date of creation')
    name: str = Field(
        ..., example='Interesting Observation', description='Title of this entry'
    )
    description: Optional[str] = Field(
        None,
        example='I discovered an correlation between air humidity level and visitor count',
        description='Details for this entry'
    )
    location: Point
    entry_type: Optional[str] = Field(None, example='A walk in the park', alias='type')
    tags: Optional[List[Tag]] = None
    comments: Optional[List[Comment]] = None
    files: Optional[List[File]] = None

class PatchEntry(Entry):
    '''
    This is a copy of `Entry` with all fields optional
    for patching existing records.
    '''
    name: Optional[str] = Field(
        None, example='Interesting Observation', description='Title of this entry'
    )
    location: Optional[Point]

# Meteo Models

class MeteoStation(BaseModel):
    station_id: str
    station_name: str
    data_src: str
    location: Point
    altitude: int

class MeteoParameter(BaseModel):
    param_id: str
    unit: str
    description: str

class MeteoDataset(BaseModel):
    param_id: str
    unit: str
    description: str
    station_id: str
    station_name: str
    data_src: str

class MeteoMeasurements(BaseModel):
    time: List[datetime]
    value: List[float]

class MeteoMeasurementTimeOfDay(BaseModel):
    minute_of_day: List[int]
    value: List[float]

class MeteoSummary(BaseModel):
    maximum: float
    minimum: float
    mean: float
    median: float
    q1: float
    q3: float
    range: float
    variance: float
    stddev: float
    min_time: datetime
    max_time: datetime
    count: int

# Birds

class TimeSeriesResult(BaseModel):
    bucket: List[datetime]
    detections: List[int]

class DetectionLocationResult(BaseModel):
    location: Point
    detections: int
    deployment_id: int

# Walks

class SectionText(BaseModel):
    text_id: int
    walk_id: int
    percent_in: int
    percent_out: int
    title: Optional[str]
    text: Optional[str]


class PollinatorTypeEnum(str, Enum):
    fliege = "fliege"
    honigbiene = "honigbiene"
    hummel  = "hummel"
    schwebfliege = "schwebfliege"
    wildbiene = "wildbiene"
