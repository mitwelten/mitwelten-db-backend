import sqlalchemy

from api.config import crd
from api.dependencies import GeometryPoint

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import TSTZRANGE

metadata = sqlalchemy.MetaData(schema=crd.db.schema)
metadata_cache = sqlalchemy.MetaData(schema=crd.db_cache.schema)


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
    sqlalchemy.Column('order',       sqlalchemy.String),
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
    sqlalchemy.Column('order_id',    sqlalchemy.Integer),
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

mm_tags_deployments = sqlalchemy.Table(
    'mm_tags_deployments',
    metadata,
    sqlalchemy.Column('tags_tag_id',               None, ForeignKey(tags.c.tag_id)),
    sqlalchemy.Column('deployments_deployment_id', None, ForeignKey(deployments.c.deployment_id)),
    schema=crd.db.schema
)

mm_tags_entries = sqlalchemy.Table(
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

files_entry = sqlalchemy.Table(
    'files_entry',
    metadata,
    sqlalchemy.Column('file_id',     sqlalchemy.Integer,     primary_key=True),
    sqlalchemy.Column('entry_id',    None,                   ForeignKey(entries.c.entry_id, ondelete='CASCADE')),
    sqlalchemy.Column('object_name', sqlalchemy.String(255), nullable=False), # file url in S3
    sqlalchemy.Column('name',        sqlalchemy.String(255), nullable=False),
    sqlalchemy.Column('type',        sqlalchemy.String(255), nullable=False),
    sqlalchemy.Column('created_at',  sqlalchemy.TIMESTAMP,   nullable=True),
    sqlalchemy.Column('updated_at',  sqlalchemy.TIMESTAMP,   nullable=True),
    schema=crd.db.schema
)

data_pax = sqlalchemy.Table(
    'sensordata_pax',
    metadata,
    sqlalchemy.Column('time', sqlalchemy.TIMESTAMP, nullable=False),
    sqlalchemy.Column('deployment_id', None, ForeignKey(deployments.c.deployment_id)),
    sqlalchemy.Column('pax', sqlalchemy.Integer, nullable=False),
    sqlalchemy.Column('voltage', sqlalchemy.Float, nullable=False),
)

data_env = sqlalchemy.Table(
    'sensordata_env',
    metadata,
    sqlalchemy.Column('time', sqlalchemy.TIMESTAMP, nullable=False),
    sqlalchemy.Column('deployment_id', None, ForeignKey(deployments.c.deployment_id)),
    sqlalchemy.Column('temperature', sqlalchemy.Float, nullable=False),
    sqlalchemy.Column('humidity', sqlalchemy.Float, nullable=False),
    sqlalchemy.Column('moisture', sqlalchemy.Float, nullable=False),
    sqlalchemy.Column('voltage', sqlalchemy.Float, nullable=False),
)

# Meteo

meteo_station = sqlalchemy.Table(
    "station",
    metadata_cache,
    sqlalchemy.Column("station_id", sqlalchemy.Text, primary_key=True),
    sqlalchemy.Column("station_name", sqlalchemy.Text, nullable=False),
    sqlalchemy.Column("data_src", sqlalchemy.Text, nullable=False),
    sqlalchemy.Column("location", GeometryPoint, nullable=False),
    sqlalchemy.Column("altitude", sqlalchemy.Integer, nullable=False),
    schema=crd.db_cache.schema,
)


meteo_parameter = sqlalchemy.Table(
    "parameter",
    metadata_cache,
    sqlalchemy.Column("param_id", sqlalchemy.Text, primary_key=True),
    sqlalchemy.Column("unit", sqlalchemy.Text, nullable=False),
    sqlalchemy.Column("description", sqlalchemy.Text, nullable=False),
    schema=crd.db_cache.schema,
)

meteo_meteodata = sqlalchemy.Table(
    "meteodata",
    metadata_cache,
    sqlalchemy.Column("ts", sqlalchemy.TIMESTAMP, nullable=False),
    sqlalchemy.Column("param_id", None, ForeignKey(meteo_parameter.c.param_id)),
    sqlalchemy.Column("station_id", None, ForeignKey(meteo_station.c.station_id)),
    sqlalchemy.Column("value", sqlalchemy.Float, nullable=False),
    schema=crd.db_cache.schema,
)

# Walk

walk = sqlalchemy.Table(
    'walk',
    metadata,
    sqlalchemy.Column('walk_id'     , sqlalchemy.Integer,   primary_key=True),
    sqlalchemy.Column('title'       , sqlalchemy.Text,      nullable=True),
    sqlalchemy.Column('description' , sqlalchemy.Text,      nullable=True),
    sqlalchemy.Column('path'        , sqlalchemy.ARRAY(sqlalchemy.FLOAT), nullable=True),
    sqlalchemy.Column('created_at'  , sqlalchemy.TIMESTAMP, nullable=False),
    sqlalchemy.Column('updated_at'  , sqlalchemy.TIMESTAMP, nullable=True),
    schema=crd.db.schema,
)


walk_text = sqlalchemy.Table(
    'walk_text',
    metadata,
    sqlalchemy.Column('text_id'     , sqlalchemy.Integer,   primary_key=True),
    sqlalchemy.Column('walk_id'     , sqlalchemy.Integer,   nullable=False),
    sqlalchemy.Column('percent_in'  , sqlalchemy.Integer,   nullable=False),
    sqlalchemy.Column('percent_out' , sqlalchemy.Integer,   nullable=False),
    sqlalchemy.Column('title'       , sqlalchemy.Text,      nullable=True),
    sqlalchemy.Column('text'        , sqlalchemy.Text,      nullable=True),
    sqlalchemy.Column('created_at'  , sqlalchemy.TIMESTAMP, nullable=False),
    sqlalchemy.Column('updated_at'  , sqlalchemy.TIMESTAMP, nullable=True),
    schema=crd.db.schema,
)

# Explore

user_collections = sqlalchemy.Table(
    'user_collections',
    metadata,
    sqlalchemy.Column('user_sub'    , sqlalchemy.Text,      primary_key=False),
    sqlalchemy.Column('datasets'    , sqlalchemy.JSON,      nullable=True),
    schema=crd.db.schema,
)

annotations = sqlalchemy.Table(
    'annotations',
    metadata,
    sqlalchemy.Column('annot_id'    , sqlalchemy.Integer,   nullable=False),
    sqlalchemy.Column('title'       , sqlalchemy.Text,      nullable=False),
    sqlalchemy.Column('user_sub'    , sqlalchemy.Text,      nullable=False),
    sqlalchemy.Column('created_at'  , sqlalchemy.TIMESTAMP, nullable=False),
    sqlalchemy.Column('updated_at'  , sqlalchemy.TIMESTAMP, nullable=False),
    sqlalchemy.Column('content'     , sqlalchemy.Text,      nullable=True),
    sqlalchemy.Column('url'         , sqlalchemy.Text,      nullable=True),
    sqlalchemy.Column('datasets'    , sqlalchemy.JSON,      nullable=True),
    schema=crd.db.schema,
)

user_entity = sqlalchemy.Table(
    'user_entity',
    metadata,
    sqlalchemy.Column('id'          , sqlalchemy.Text,      nullable=False),
    sqlalchemy.Column('email'       , sqlalchemy.Text,      nullable=False),
    sqlalchemy.Column('first_name'  , sqlalchemy.Text,      nullable=False),
    sqlalchemy.Column('last_name'   , sqlalchemy.Text,      nullable=False),
    sqlalchemy.Column('username'    , sqlalchemy.Text,      nullable=False),
    schema=crd.db.schema,
)
