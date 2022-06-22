import sys
import re
import sqlalchemy

# from geoalchemy2 import Geometry
from asyncpg.pgproto.types import Point as PgPoint

from sqlalchemy import func, ForeignKey
from sqlalchemy.types import UserDefinedType, Float

sys.path.append('../../')
import credentials as crd

class GeometryPoint(UserDefinedType):

    def get_col_spec(self):
        return "POINT"

    def bind_expression(self, bindvalue):
        return func.Point(bindvalue, type_=self)

    def column_expression(self, col):
        return col

    def bind_processor(self, dialect):
        def process(value):
            if value is None:
                return None
            assert isinstance(value, tuple)
            lat, lon = value
            return "POINT(%s, %s)" % (lat, lon)
        return process

    def result_processor(self, dialect, coltype):
        def process(value):
            if value is None:
                return None
            assert isinstance(value, PgPoint)
            return {'lat': float(value.x), 'lon': float(value.y)}
        return process

metadata = sqlalchemy.MetaData(schema=crd.db.schema)

location = sqlalchemy.Table(
    'locations',
    metadata,
    sqlalchemy.Column('location_id', sqlalchemy.Integer,     primary_key=True),
    sqlalchemy.Column('location',    GeometryPoint,          nullable=False),
    sqlalchemy.Column('type',        sqlalchemy.String(255), nullable=True),
    sqlalchemy.Column('name',        sqlalchemy.String(255), nullable=False),
    sqlalchemy.Column('description', sqlalchemy.Text,        nullable=True),
    # sqlalchemy.Column('created_at',  sqlalchemy.TIMESTAMP,   nullable=False),
    # sqlalchemy.Column('updated_at',  sqlalchemy.TIMESTAMP,   nullable=False),
    schema=crd.db.schema
)

entry = sqlalchemy.Table(
    'entries',
    metadata,
    sqlalchemy.Column('entry_id',    sqlalchemy.Integer,     primary_key=True),
    sqlalchemy.Column('location_id', None,                   ForeignKey('locations.location_id')),
    sqlalchemy.Column('name',        sqlalchemy.String(255), nullable=False),
    sqlalchemy.Column('description', sqlalchemy.Text,        nullable=True),
    sqlalchemy.Column('type',        sqlalchemy.String(255), nullable=True),
    sqlalchemy.Column('created_at',  sqlalchemy.TIMESTAMP,   nullable=False),
    sqlalchemy.Column('updated_at',  sqlalchemy.TIMESTAMP,   nullable=False),
    schema=crd.db.schema
)





# # create the tables if they don't exists
# # not useful in this case
# metadata.create_all(engine)
