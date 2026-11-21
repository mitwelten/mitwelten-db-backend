from datetime import datetime
from enum import Enum
from typing import List, Literal, Optional, Tuple, Union

from asyncpg.types import Range
from pydantic import BaseModel, ConfigDict, Field, PositiveInt, RootModel, constr, field_serializer
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
end timestamp"):

```sql
['2021-09-12 00:00:00+02:00','2021-10-15 00:00:00+02:00')
```

The pydantic model / type definition also converts this `tstzrange` back into
the aforementioned format when retrieving (using as a response model).
'''
    start: Optional[datetime] = Field(None, examples=['2021-09-11T22:00:00+00:00'], title='Beginning of period (inclusive)')
    end: Optional[datetime] = Field(None, examples=['2021-10-14T22:00:00Z'], title='End of period (non inclusive)')

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
    def validate_type(cls, val):
        if isinstance(val, Range):
            return {'start': val.lower, 'end': val.upper}
        lower = None
        upper = None
        if val.get('start'):
            lower = datetime.fromisoformat(cls.stripz(val['start']))
        if val.get('end'):
            upper = datetime.fromisoformat(cls.stripz(val['end']))
        return Range(lower=lower, upper=upper)

    def __repr__(self):
        return f'TimeStampRange({super().__repr__()})'

class DeleteResponse(BaseModel):
    status: str
    id: int

class ValidationResult(RootModel[bool]):
    ...

class NodeValidationRequest(BaseModel):
    node_id: Optional[int] = None
    node_label: str

class ImageValidationRequest(BaseModel):
    sha256: str
    node_label: str
    timestamp: datetime

    @field_serializer('timestamp', when_used='json')
    def serialize_timestamp(self, v: datetime):
        return v.timestamp()

class ImageValidationResponse(BaseModel):
    hash_match: bool
    object_name_match: bool
    object_name: str
    node_deployed: bool
    deployment_id: Optional[int] = None

class AudioValidationRequest(ImageValidationRequest):
    ...

class AudioValidationResponse(ImageValidationResponse):
    ...


class ImageRequest(BaseModel):
    object_name: str
    sha256: str
    timestamp: datetime
    deployment_id: int
    file_size: int
    resolution: Tuple[PositiveInt, PositiveInt]

    @field_serializer('timestamp', when_used='json')
    def serialize_timestamp(self, v: datetime):
        return v.timestamp()

class AudioRequest(BaseModel):
    object_name: str
    sha256: str
    timestamp: datetime = Field(..., alias='time')
    deployment_id: int
    file_size: int
    audio_format: str = Field(..., alias='format')
    bit_depth: int
    channels: int
    duration: float
    sample_rate: int
    serial_number: str
    source: str
    gain: str
    filter_: str = Field(..., alias='filter')
    amp_thresh: Optional[str] = None
    amp_trig: Optional[str] = None
    battery: float
    temperature: float
    rec_end_status: str

    model_config = ConfigDict(populate_by_name=True)

    @field_serializer('timestamp', when_used='json')
    def serialize_timestamp(self, v: datetime):
        return v.timestamp()

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
    lat: float = Field(..., examples=[47.53484943172696], title='Latitude (WGS84)')
    lon: float = Field(..., examples=[7.612519197679952], title='Longitude (WGS84)')

class ResultFull(Species):
    location: Point
    object_name: str
    object_time: datetime
    time_start_relative: float
    duration: float
    image_url: Optional[str] = None
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
    image_url: Optional[str] = None

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
    label_de: Optional[str] = None
    label_en: Optional[str] = None
    image_url: Optional[str] = None
    rank: RankEnum

class Tag(BaseModel):
    '''
    Annotation
    '''

    tag_id: Optional[int] = None
    name: constr(pattern=r'^\w+(?:[ :-]+\w+)*$')

class TagStats(Tag):
    '''
    Annotation with assignment count
    '''

    deployments: int
    notes: int
    created_at: datetime
    updated_at: datetime

class Node(BaseModel):
    '''
    A device deployed in the field, commondly collecting and/or processing data
    '''
    node_id: Optional[int] = None
    node_label: constr(pattern=r'^\d{4}-\d{4}$') = Field(
        ...,
        examples=['2323-4242'],
        description='Identifyer, a.k.a _Node ID_, _Node Label_, or _Label_'
    )
    node_type: str = Field(..., examples=['Audio'], description='Desription of function', alias='type')
    serial_number: Optional[str] = None
    description: Optional[str] = Field(
        None,
        examples=['Environmental sensor to record humidity, temperature and athmospheric pressure'],
    )
    platform: Optional[str] = Field(None, examples=['Audiomoth'], description='Hardware platform')
    connectivity: Optional[str] = None
    power: Optional[str] = None
    hardware_version: Optional[str] = None
    software_version: Optional[str] = None
    firmware_version: Optional[str] = None

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

class TVStackSelectionRequest(BaseModel):
    deployment_id: int
    period: TimeStampRange
    interval: Optional[int] = None
    phase: Optional[str] = None

class QueueInputDefinition(BaseModel):
    node_label: str # for now keep this required. TODO: implement update for all dask when node_label not present

class QueueUpdateDefinition(BaseModel):
    node_label: str # for now keep this required. TODO: implement update for all dask when node_label not present
    action: Literal['reset_all', 'reset_failed', 'pause', 'resume']

class File(BaseModel):
    '''
    File uploaded through front end to S3, associated to a note
    '''
    id: Optional[int] = None
    type: str = Field(title='MIME type', examples=['application/pdf'])
    name: str = Field(title='File name')
    object_name: constr(strip_whitespace=True) = Field(
        title='Link to S3 object',
        description='Constrained to project specific S3 bucket'
    )

class EnvTypeEnum(str, Enum):
    temperature = 'temperature'
    humidity = 'humidity'
    moisture = 'moisture'

class EnvDatum(BaseModel):
    '''
    Datum of a measurement by an environmental sensor
    '''
    type: Literal['env', 'HumiTemp', 'HumiTempMoisture', 'Moisture']
    time: Optional[datetime] = None
    nodeLabel: Optional[constr(pattern=r'^\d{4}-\d{4}$')] = None
    voltage: Optional[float] = Field(None, examples=[4.8])
    voltageUnit: Optional[str] = Field(None, examples=['V'])
    temperature: Optional[float] = Field(None, examples=[7.82])
    temperatureUnit: Optional[str] = Field('°C', examples=['°C'])
    humidity: Optional[float] = Field(None, examples=[93.78])
    humidityUnit: Optional[str] = Field('%', examples=['%'])
    moisture: Optional[float] = Field(None, examples=[2.6])
    moistureUnit: Optional[str] = Field('g/m³', examples=['g/m³'])

class PaxDatum(BaseModel):
    '''
    Datum of a measurement by a PAX sensor
    '''
    type: Literal['pax', 'Pax']
    time: Optional[datetime] = None
    nodeLabel: Optional[constr(pattern=r'^\d{4}-\d{4}$')] = None
    voltage: Optional[float] = Field(None, examples=[4.8])
    voltageUnit: Optional[str] = Field('V', examples=['V'])
    pax: Optional[int] = Field(None, examples=[17])
    paxUnit: Optional[str] = Field(None, examples=[''])

class Datum(RootModel[Union[EnvDatum, PaxDatum]]):
    root: Union[EnvDatum, PaxDatum] = Field(..., discriminator='type')

class DatumResponse(RootModel[Union[List[PaxDatum], List[EnvDatum]]]):
    '''
    Response containing one of a selection of sensor data types
    '''

class PaxMeasurement(BaseModel):
    time: datetime
    nodeLabel: Optional[constr(pattern=r'^\d{4}-\d{4}$')] = None
    deviceEui: Optional[str] = None
    pax: int
    voltage: float

class EnvMeasurement(BaseModel):
    time: datetime
    nodeLabel: Optional[constr(pattern=r'^\d{4}-\d{4}$')] = None
    deviceEui: Optional[str] = None
    voltage: float
    temperature: float
    humidity: float
    moisture: float

class ApiResponse(BaseModel):
    code: Optional[int] = None
    type: Optional[str] = None
    message: Optional[str] = None

class ApiErrorResponse(BaseModel):
    detail: Optional[str] = None


class Note(BaseModel):
    '''
    A user generated note than can be pinned to the map and to which `files` and `tags` can be associated
    '''
    note_id: Optional[int] = None
    date: Optional[datetime] = Field(None, examples=['2022-12-31T23:59:59.999Z'], description='Date of creation')
    title: str = Field(
        ..., examples=['Interesting Observation'], description='Title of this note'
    )
    description: Optional[str] = Field(
        None,
        examples=['I discovered an correlation between air humidity level and visitor count'],
        description='Details for this note'
    )
    public: bool = True
    location: Optional[Point] = None
    note_type: Optional[str] = Field(None, examples=['A walk in the park'], alias='type')
    tags: Optional[List[Tag]] = None
    files: Optional[List[File]] = None

class NoteResponse(Note):
    author: Optional[str] = None

class PatchNote(Note):
    '''
    This is a copy of `Note` with all fields optional
    for patching existing records.
    '''
    title: Optional[str] = Field(
        None, examples=['Interesting Observation'], description='Title of this note'
    )

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
    last_measurement: Optional[datetime] = None

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

class DetectionsByLocation(BaseModel):
    location: Point
    detections: int

class DetectionLocationResult(DetectionsByLocation):
    deployment_id: int

class BirdSpeciesCount(BaseModel):
    bucket: datetime
    species: str = Field(..., examples=['Parus major'])
    count: int = Field(..., examples=[42])

# Walks

class Walk(BaseModel):
    walk_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    path: Optional[List[Tuple[float, float]]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class SectionText(BaseModel):
    text_id: int
    walk_id: int
    percent_in: int
    percent_out: int
    title: Optional[str] = None
    text: Optional[str] = None

class HotSpot(BaseModel):
    hotspot_id: int = Field(None, alias='id')
    walk_id: int
    location: Point
    hotspot_type: int = Field(None, alias='type')
    subject: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)

class HotspotImage(HotSpot):
    title: str
    description: str

class ImageReference(BaseModel):
    url: str
    image_credits: str = Field(None, alias='credits')

class HotspotImageSingle(HotspotImage, ImageReference):
    hotspot_type: int = Field(1, alias='type')

class HotspotImageSequence(HotspotImage):
    hotspot_type: int = Field(2, alias='type')
    sequence: List[ImageReference]

class HotspotAudioText(HotSpot):
    hotspot_type: int = Field(4, alias='type')
    portraitUrl: str
    audioUrl: str
    speakerName: Optional[str] = None
    speakerFunction: Optional[str] = None
    contentSubject: Optional[str] = None

class HotspotInfotext(HotSpot):
    hotspot_type: int = Field(3, alias='type')
    title: str
    text: str

class HotspotData(HotSpot):
    hotspot_type: int = Field(6, alias='type')
    title: str
    text: str
    endpoint: str

class PaxDataPoint(BaseModel):
    tag: str
    pax_avg: float
    pax_sdev: float
    pax_min: float
    pax_max: float

class BirdsDataPoint(BaseModel):
    species: str = Field(..., alias='class')
    month: int
    count: int

class PollinatorDataPoint(BaseModel):
    class_: str = Field(..., alias='class')
    month: int
    count: int

class ChartSummaryOption(BaseModel):
    label: str
    value: int

class HotspotDataPaxResponse(BaseModel):
    datapoints: List[PaxDataPoint]
    summaryOptions: List[ChartSummaryOption]
    chart: str

class HotspotDataBirdsResponse(BaseModel):
    datapoints: List[BirdsDataPoint]
    summaryOptions: List[ChartSummaryOption]
    chart: str

class HotspotDataPollinatorsResponse(BaseModel):
    datapoints: List[PollinatorDataPoint]
    summaryOptions: List[ChartSummaryOption]
    chart: str

class PollinatorTypeEnum(str, Enum):
    fliege = 'fliege'
    honigbiene = 'honigbiene'
    hummel  = 'hummel'
    schwebfliege = 'schwebfliege'
    wildbiene = 'wildbiene'

class AnnotationText(BaseModel):
    content:str

class AnnotationContent(BaseModel):
    title: str
    user_sub: str
    created_at: datetime
    updated_at: datetime
    content: str
    url: str
    datasets: Optional[str] = None

class Annotation(AnnotationContent):
    id: int
    username: str
    full_name: str

class EnvironmentRawEntry(BaseModel):
    environment_id: Optional[int] = None
    location: Point
    timestamp: datetime
    attribute_01: Optional[int] = None
    attribute_02: Optional[int] = None
    attribute_03: Optional[int] = None
    attribute_04: Optional[int] = None
    attribute_05: Optional[int] = None
    attribute_06: Optional[int] = None
    attribute_07: Optional[int] = None
    attribute_08: Optional[int] = None
    attribute_09: Optional[int] = None
    attribute_10: Optional[int] = None

class EnvironmentEntry(EnvironmentRawEntry):
    environment_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    distance: Optional[float] = None
