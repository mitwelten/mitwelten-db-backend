import sys
import sqlalchemy

from asyncpg.pgproto.types import Point as PgPoint

from sqlalchemy import func, ForeignKey
from sqlalchemy.dialects.postgresql import TSTZRANGE
from sqlalchemy.types import UserDefinedType

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

# view: birdnet_input
birdnet_input = sqlalchemy.Table(
    'birdnet_input',
    metadata,
    sqlalchemy.Column('file_id',      sqlalchemy.Integer   , primary_key=True),
    sqlalchemy.Column('object_name',  sqlalchemy.Text      , nullable=False),
    sqlalchemy.Column('time',         sqlalchemy.TIMESTAMP , nullable=False),
    sqlalchemy.Column('file_size',    sqlalchemy.Integer   , nullable=False),
    sqlalchemy.Column('sample_rate',  sqlalchemy.Integer   , nullable=False),
    sqlalchemy.Column('node_label',   sqlalchemy.String(32), nullable=False),
    sqlalchemy.Column('duration',     sqlalchemy.REAL      , nullable=False),
    sqlalchemy.Column('location',     GeometryPoint        , nullable=False)
)

results = sqlalchemy.Table(
    'birdnet_results',
    metadata,
    sqlalchemy.Column('result_id',    sqlalchemy.Integer    , primary_key=True),
    sqlalchemy.Column('file_id',      sqlalchemy.Integer    , nullable=False),
    sqlalchemy.Column('time_start',   sqlalchemy.REAL       , nullable=False),
    sqlalchemy.Column('time_end',     sqlalchemy.REAL       , nullable=False),
    sqlalchemy.Column('confidence',   sqlalchemy.REAL       , nullable=False),
    sqlalchemy.Column('species',      sqlalchemy.String(255), nullable=False)
)

species = sqlalchemy.Table(
    'birdnet_inferred_species',
    metadata,
    sqlalchemy.Column('species',    sqlalchemy.String(255)),
    sqlalchemy.Column('confidence', sqlalchemy.REAL),
    sqlalchemy.Column('time_start', sqlalchemy.TIMESTAMP)
)

species_day = sqlalchemy.Table(
    'birdnet_inferred_species_day',
    metadata,
    sqlalchemy.Column('species',    sqlalchemy.String(255)),
    sqlalchemy.Column('confidence', sqlalchemy.REAL),
    sqlalchemy.Column('date',       sqlalchemy.String)
)

results_file_taxonomy = sqlalchemy.Table(
    'birdnet_inferred_species_file_taxonomy',
    metadata,
    sqlalchemy.Column('species',     sqlalchemy.String(255)),
    sqlalchemy.Column('location',    GeometryPoint),
    sqlalchemy.Column('confidence',  sqlalchemy.REAL),
    sqlalchemy.Column('object_name', sqlalchemy.String),
    sqlalchemy.Column('object_time', sqlalchemy.TIMESTAMP),
    sqlalchemy.Column('time_start_relative', sqlalchemy.REAL),
    sqlalchemy.Column('duration',    sqlalchemy.REAL),
    sqlalchemy.Column('time_start',  sqlalchemy.TIMESTAMP),
    sqlalchemy.Column('image_url',   sqlalchemy.String),
    sqlalchemy.Column('species_de',  sqlalchemy.String),
    sqlalchemy.Column('species_en',  sqlalchemy.String),
    sqlalchemy.Column('genus',       sqlalchemy.String),
    sqlalchemy.Column('family',      sqlalchemy.String),
    sqlalchemy.Column('class',       sqlalchemy.String),
    sqlalchemy.Column('phylum',      sqlalchemy.String),
    sqlalchemy.Column('kingdom',     sqlalchemy.String)
)

taxonomy_tree = sqlalchemy.Table(
    'taxonomy_tree',
    metadata,
    sqlalchemy.Column('species_id',  sqlalchemy.Integer),
    sqlalchemy.Column('genus_id',    sqlalchemy.Integer),
    sqlalchemy.Column('family_id',   sqlalchemy.Integer),
    sqlalchemy.Column('class_id',    sqlalchemy.Integer),
    sqlalchemy.Column('phylum_id',   sqlalchemy.Integer),
    sqlalchemy.Column('kingdom_id',  sqlalchemy.Integer),
)

taxonomy_data = sqlalchemy.Table(
    'taxonomy_data',
    metadata,
    sqlalchemy.Column('datum_id',    sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column('label_sci',   sqlalchemy.String(255)),
    sqlalchemy.Column('label_de',    sqlalchemy.String(255)),
    sqlalchemy.Column('label_en',    sqlalchemy.String(255)),
    sqlalchemy.Column('image_url',   sqlalchemy.String(255)),
    sqlalchemy.Column('created_at',  sqlalchemy.TIMESTAMP, nullable=False),
    sqlalchemy.Column('updated_at',  sqlalchemy.TIMESTAMP, nullable=False),
)

tasks = sqlalchemy.Table(
    'birdnet_tasks',
    metadata,
    sqlalchemy.Column('task_id',        sqlalchemy.Integer    , primary_key=True),
    sqlalchemy.Column('file_id',        None                  , sqlalchemy.ForeignKey('birdnet_input.file_id')),
    sqlalchemy.Column('config_id',      sqlalchemy.Integer    , nullable=False),
    sqlalchemy.Column('state',          sqlalchemy.Integer    , nullable=False),
    sqlalchemy.Column('scheduled_on',   sqlalchemy.TIMESTAMP  , nullable=False),
    sqlalchemy.Column('pickup_on',      sqlalchemy.TIMESTAMP  , nullable=False),
    sqlalchemy.Column('end_on',         sqlalchemy.TIMESTAMP  , nullable=False),
    sqlalchemy.Column('batch_id',       sqlalchemy.Integer,     nullable=False),
    schema=crd.db.schema
)

nodes = sqlalchemy.Table(
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

deployments = sqlalchemy.Table(
    'deployments',
    metadata,
    sqlalchemy.Column('deployment_id', sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column('node_id',       None,               sqlalchemy.ForeignKey('nodes.node_id')),
    sqlalchemy.Column('location',      GeometryPoint,      nullable=False),
    sqlalchemy.Column('description',   sqlalchemy.Text,    nullable=True),
    sqlalchemy.Column('period',        TSTZRANGE,          nullable=False),
    schema=crd.db.schema
)

entries = sqlalchemy.Table(
    'entries',
    metadata,
    sqlalchemy.Column('entry_id',    sqlalchemy.Integer,     primary_key=True),
    sqlalchemy.Column('location',    GeometryPoint,          nullable=False),
    sqlalchemy.Column('name',        sqlalchemy.String(255), nullable=False),
    sqlalchemy.Column('description', sqlalchemy.Text,        nullable=True),
    sqlalchemy.Column('type',        sqlalchemy.String(255), nullable=True),
    sqlalchemy.Column('created_at',  sqlalchemy.TIMESTAMP,   nullable=False),
    sqlalchemy.Column('updated_at',  sqlalchemy.TIMESTAMP,   nullable=False),
    schema=crd.db.schema
)

tags = sqlalchemy.Table(
    'tags',
    metadata,
    sqlalchemy.Column('tag_id',      sqlalchemy.Integer,     primary_key=True),
    sqlalchemy.Column('name',        sqlalchemy.String(255), nullable=False),
    sqlalchemy.Column('created_at',  sqlalchemy.TIMESTAMP,   nullable=False),
    sqlalchemy.Column('updated_at',  sqlalchemy.TIMESTAMP,   nullable=False),
    schema=crd.db.schema
)

mm_tag_deployments = sqlalchemy.Table(
    'mm_tags_deployments',
    metadata,
    sqlalchemy.Column('tags_tag_id',               None, ForeignKey(tags.c.tag_id)),
    sqlalchemy.Column('deployments_deployment_id', None, ForeignKey(deployments.c.deployment_id)),
    schema=crd.db.schema
)

mm_tag_entries = sqlalchemy.Table(
    'mm_tags_entries',
    metadata,
    sqlalchemy.Column('tags_tag_id',               None, ForeignKey(tags.c.tag_id)),
    sqlalchemy.Column('entries_entry_id',          None, ForeignKey(entries.c.entry_id)),
    schema=crd.db.schema
)

data_records = sqlalchemy.Table(
    'data_records', # this is a view!
    metadata,
    sqlalchemy.Column('record_id',      sqlalchemy.Integer),
    sqlalchemy.Column('deployment_id',  sqlalchemy.Integer),
    sqlalchemy.Column('type',           sqlalchemy.String(255)),
    schema=crd.db.schema
)

files_image = sqlalchemy.Table(
    'files_image',
    metadata,
    sqlalchemy.Column('file_id',        sqlalchemy.Integer,                   primary_key=True),
    sqlalchemy.Column('object_name',    sqlalchemy.Text,                      nullable=False),
    sqlalchemy.Column('sha256',         sqlalchemy.String(64),                nullable=False),
    sqlalchemy.Column('time',           sqlalchemy.TIMESTAMP,                 nullable=False),
    sqlalchemy.Column('deployment_id',  sqlalchemy.ForeignKey('deployments.deployment_id')),
    sqlalchemy.Column('file_size',      sqlalchemy.Integer,                   nullable=False),
    sqlalchemy.Column('resolution',     sqlalchemy.ARRAY(sqlalchemy.Integer), nullable=False),
    sqlalchemy.Column('created_at',     sqlalchemy.TIMESTAMP(timezone=True),  nullable=False),
    sqlalchemy.Column('updated_at',     sqlalchemy.TIMESTAMP(timezone=True),  nullable=False),
)
