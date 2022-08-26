import sys
import re
import sqlalchemy

# from geoalchemy2 import Geometry
from asyncpg.pgproto.types import Point as PgPoint
from sqlalchemy.dialects.postgresql import TSTZRANGE

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

tag = sqlalchemy.Table(
    'tags',
    metadata,
    sqlalchemy.Column('tag_id',      sqlalchemy.Integer,     primary_key=True),
    sqlalchemy.Column('name',        sqlalchemy.String(255), nullable=False),
    sqlalchemy.Column('created_at',  sqlalchemy.TIMESTAMP,   nullable=False),
    sqlalchemy.Column('updated_at',  sqlalchemy.TIMESTAMP,   nullable=False),
    schema=crd.db.schema
)

file = sqlalchemy.Table(
    'files_entry',
    metadata,
    sqlalchemy.Column('file_id',     sqlalchemy.Integer,     primary_key=True),
    sqlalchemy.Column('entry_id',    None,                   ForeignKey(entry.c.entry_id, ondelete='CASCADE')),
    sqlalchemy.Column('object_name', sqlalchemy.String(255), nullable=False), # file url in S3
    sqlalchemy.Column('name',        sqlalchemy.String(255), nullable=False),
    sqlalchemy.Column('type',        sqlalchemy.String(255), nullable=False),
    sqlalchemy.Column('created_at',  sqlalchemy.TIMESTAMP,   nullable=True),
    sqlalchemy.Column('updated_at',  sqlalchemy.TIMESTAMP,   nullable=True),
    schema=crd.db.schema
)

node = sqlalchemy.Table(
    'nodes',
    metadata,
    sqlalchemy.Column('node_id',            sqlalchemy.Integer,     primary_key=True),
    sqlalchemy.Column('node_label',         sqlalchemy.String(32),  nullable=False),
    sqlalchemy.Column('type',               sqlalchemy.String(128), nullable=False),
    sqlalchemy.Column('serial_number',      sqlalchemy.String(128), nullable=True),
    sqlalchemy.Column('description',        sqlalchemy.Text,        nullable=True),
    sqlalchemy.Column('platform',           sqlalchemy.String(128), nullable=True),
    sqlalchemy.Column('connectivity',       sqlalchemy.String(128), nullable=True),
    sqlalchemy.Column('power',              sqlalchemy.String(128), nullable=True),
    sqlalchemy.Column('hardware_version',   sqlalchemy.String(128), nullable=True),
    sqlalchemy.Column('software_version',   sqlalchemy.String(128), nullable=True),
    sqlalchemy.Column('firmware_version',   sqlalchemy.String(128), nullable=True),
    sqlalchemy.Column('created_at',         sqlalchemy.TIMESTAMP,   nullable=False),
    sqlalchemy.Column('updated_at',         sqlalchemy.TIMESTAMP,   nullable=False),
    schema=crd.db.schema
)

deployment = sqlalchemy.Table(
    'deployments',
    metadata,
    sqlalchemy.Column('deployment_id', sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column('node_id',       None,               sqlalchemy.ForeignKey('nodes.node_id')),
    sqlalchemy.Column('location_id',   None,               sqlalchemy.ForeignKey('locations.location_id')),
    sqlalchemy.Column('period',        TSTZRANGE,          nullable=False),
    # sqlalchemy.Column('created_at',    sqlalchemy.TIMESTAMP(timezone=True),  nullable=False),
    # sqlalchemy.Column('updated_at',    sqlalchemy.TIMESTAMP(timezone=True),  nullable=False),
    schema=crd.db.schema
)

datum_pax = sqlalchemy.Table(
    'sensordata_pax',
    metadata,
    sqlalchemy.Column('time', sqlalchemy.TIMESTAMP, nullable=False),
    sqlalchemy.Column('node_id', None, ForeignKey(node.c.node_id)),
    sqlalchemy.Column('location_id', None, ForeignKey(location.c.location_id)),
    sqlalchemy.Column('pax', sqlalchemy.Integer, nullable=False),
    sqlalchemy.Column('voltage', sqlalchemy.Float, nullable=False),
)

datum_env = sqlalchemy.Table(
    'sensordata_env',
    metadata,
    sqlalchemy.Column('time', sqlalchemy.TIMESTAMP, nullable=False),
    sqlalchemy.Column('node_id', None, ForeignKey(node.c.node_id)),
    sqlalchemy.Column('location_id', None, ForeignKey(location.c.location_id)),
    sqlalchemy.Column('temperature', sqlalchemy.Float, nullable=False),
    sqlalchemy.Column('humidity', sqlalchemy.Float, nullable=False),
    sqlalchemy.Column('moisture', sqlalchemy.Float, nullable=False),
    sqlalchemy.Column('voltage', sqlalchemy.Float, nullable=False),
)

mm_tag_entry = sqlalchemy.Table(
    'mm_tags_entries',
    metadata,
    sqlalchemy.Column('tags_tag_id',      None, ForeignKey(tag.c.tag_id)),
    sqlalchemy.Column('entries_entry_id', None, ForeignKey(entry.c.entry_id)),
    schema=crd.db.schema
)



# # create the tables if they don't exists
# # not useful in this case
# metadata.create_all(engine)
