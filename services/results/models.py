from typing import Optional
from datetime import datetime
from sqlalchemy.dialects.postgresql import TSTZRANGE
from pydantic import BaseModel
from asyncpg.types import Range

class TimeStampRange(TSTZRANGE):

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
            if val['start'] != '':
                lower = datetime.fromisoformat(val['start'])
            if val['end'] != '':
                upper = datetime.fromisoformat(val['end'])
            return Range(lower=lower, upper=upper)

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

class Deployment(BaseModel):
    '''
    Deployment
    '''

    deployment_id: Optional[int] = None
    node_id: int
    location_id: int
    period: TimeStampRange
