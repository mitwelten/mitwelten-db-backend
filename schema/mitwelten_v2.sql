--
-- Mitwelten Database - Schema V2.4
--

-- search/replace "dev" by target schema
SET SEARCH_PATH = "dev";

BEGIN;

-- DROP SCHEMA "dev" CASCADE;

CREATE SCHEMA IF NOT EXISTS "dev"
    AUTHORIZATION mitwelten_admin;

CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS postgres_fdw;

CREATE TABLE IF NOT EXISTS birdnet_configs
(
    config_id serial,
    config jsonb NOT NULL,
    comment text,
    created_at timestamptz NOT NULL DEFAULT current_timestamp,
    updated_at timestamptz NOT NULL DEFAULT current_timestamp,
    PRIMARY KEY (config_id),
    UNIQUE (config)
);

CREATE TABLE IF NOT EXISTS files_audio
(
    file_id serial,
    object_name text NOT NULL,
    sha256 character varying(64) NOT NULL,
    time timestamptz NOT NULL,
    deployment_id integer NOT NULL,
    duration double precision NOT NULL,
    serial_number character varying(32),
    format character varying(64),
    file_size bigint NOT NULL,
    sample_rate integer NOT NULL,
    bit_depth smallint,
    channels smallint,
    battery real,
    temperature real,
    gain character varying(32),
    filter character varying(64),
    source character varying(32),
    rec_end_status character varying(32),
    comment character varying(64),
    class character varying(32),
    created_at timestamptz NOT NULL DEFAULT current_timestamp,
    updated_at timestamptz NOT NULL DEFAULT current_timestamp,
    PRIMARY KEY (file_id),
    UNIQUE (object_name),
    UNIQUE (sha256)
);

CREATE TABLE IF NOT EXISTS files_image
(
    file_id serial,
    object_name text NOT NULL,
    sha256 character varying(64) NOT NULL,
    time timestamptz NOT NULL,
    deployment_id integer NOT NULL,
    file_size integer NOT NULL,
    resolution integer[] NOT NULL,
    created_at timestamptz NOT NULL DEFAULT current_timestamp,
    updated_at timestamptz NOT NULL DEFAULT current_timestamp,
    PRIMARY KEY (file_id),
    UNIQUE (object_name),
    UNIQUE (sha256)
);

CREATE TABLE IF NOT EXISTS birdnet_results
(
    result_id serial,
    task_id integer NOT NULL,
    file_id integer NOT NULL,
    time_start real NOT NULL,
    time_end real NOT NULL,
    confidence real NOT NULL,
    species character varying(255) NOT NULL,
    PRIMARY KEY (result_id)
);

CREATE TABLE IF NOT EXISTS birdnet_species_occurrence
(
    id serial,
    species character varying(255) NOT NULL,
    occurence integer,
    unlikely boolean,
    comment text,
    created_at timestamptz NOT NULL DEFAULT current_timestamp,
    updated_at timestamptz NOT NULL DEFAULT current_timestamp,
    PRIMARY KEY (id),
    UNIQUE (species)
);

CREATE TABLE IF NOT EXISTS birdnet_tasks
(
    task_id serial,
    file_id integer NOT NULL,
    config_id integer NOT NULL,
    batch_id integer,
    state integer NOT NULL,
    scheduled_on timestamptz NOT NULL,
    pickup_on timestamptz,
    end_on timestamptz,
    PRIMARY KEY (task_id),
    CONSTRAINT unique_task_in_batch UNIQUE (file_id, config_id, batch_id)
);

-- batdetect2 SpectrogramParameters, ModelParameters, ProcessingConfiguration
CREATE TABLE IF NOT EXISTS batnet_configs
(
    config_id serial,
    config jsonb NOT NULL,
    comment text,
    created_at timestamptz NOT NULL DEFAULT current_timestamp,
    updated_at timestamptz NOT NULL DEFAULT current_timestamp,
    PRIMARY KEY (config_id),
    UNIQUE (config)
);

CREATE TABLE IF NOT EXISTS batnet_tasks
(
    task_id serial,
    file_id integer NOT NULL,
    config_id integer NOT NULL,
    state integer NOT NULL,
    scheduled_on timestamptz NOT NULL,
    pickup_on timestamptz,
    end_on timestamptz,
    PRIMARY KEY (task_id),
    CONSTRAINT unique_task UNIQUE (file_id, config_id),
    CONSTRAINT batnet_tasks_config_id_fkey FOREIGN KEY (config_id)
        REFERENCES batnet_configs (config_id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE RESTRICT,
    CONSTRAINT batnet_tasks_file_id_fkey FOREIGN KEY (file_id)
        REFERENCES files_audio (file_id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS batnet_results
(
    result_id serial,
    task_id integer NOT NULL,
    file_id integer NOT NULL,

    class character varying(128),
    event character varying(128),
    individual integer,
    class_prob real,
    det_prob real,
    start_time real,
    end_time real,
    high_freq real,
    low_freq real,

    PRIMARY KEY (result_id),
    CONSTRAINT batnet_results_file_id_fkey FOREIGN KEY (file_id)
        REFERENCES files_audio (file_id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE NO ACTION
        NOT VALID,
    CONSTRAINT batnet_results_task_id_fkey FOREIGN KEY (task_id)
        REFERENCES batnet_tasks (task_id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE NO ACTION
        NOT VALID
);

CREATE TABLE IF NOT EXISTS nodes
(
    node_id serial,
    node_label character varying(32) NOT NULL,
    type character varying(128) NOT NULL,
    serial_number character varying(128),
    platform character varying(128),
    connectivity character varying(128),
    power character varying(128),
    hardware_version character varying(128),
    software_version character varying(128),
    firmware_version character varying(128),
    description text,
    created_at timestamptz NOT NULL DEFAULT current_timestamp,
    updated_at timestamptz NOT NULL DEFAULT current_timestamp,
    PRIMARY KEY (node_id),
    UNIQUE (node_label)
);

CREATE TABLE IF NOT EXISTS deployments
(
    deployment_id serial,
    node_id integer NOT NULL,
    location point NOT NULL,
    description text,
    period tstzrange NOT NULL DEFAULT tstzrange('-infinity', 'infinity'),
    PRIMARY KEY (deployment_id),
    EXCLUDE USING GIST (node_id WITH =, period WITH &&)
);

CREATE TABLE IF NOT EXISTS sensordata_env
(
    time timestamptz NOT NULL,
    deployment_id integer NOT NULL,
    temperature double precision,
    humidity double precision,
    moisture double precision,
    voltage real
);

CREATE TABLE IF NOT EXISTS sensordata_pax
(
    time timestamptz NOT NULL,
    deployment_id integer NOT NULL,
    pax integer NOT NULL,
    voltage real
);

CREATE TABLE IF NOT EXISTS notes
(
    note_id serial,
    location point,
    title character varying(255),
    description text,
    type character varying(255),
    user_sub text NOT NULL,
    public boolean NOT NULL DEFAULT FALSE,
    created_at timestamptz NOT NULL DEFAULT current_timestamp,
    updated_at timestamptz NOT NULL DEFAULT current_timestamp,
    PRIMARY KEY (note_id)
);

CREATE TABLE IF NOT EXISTS tags
(
    tag_id serial,
    name character varying(255) NOT NULL,
    created_at timestamptz DEFAULT current_timestamp,
    updated_at timestamptz DEFAULT current_timestamp,
    PRIMARY KEY (tag_id),
    UNIQUE (name)
);

CREATE TABLE IF NOT EXISTS mm_tags_notes
(
    tags_tag_id integer,
    notes_note_id integer,
    PRIMARY KEY (tags_tag_id, notes_note_id)
);

CREATE TABLE IF NOT EXISTS mm_tags_deployments
(
    tags_tag_id integer,
    deployments_deployment_id integer,
    PRIMARY KEY (tags_tag_id, deployments_deployment_id)
);

CREATE TABLE IF NOT EXISTS files_note
(
    file_id serial,
    note_id integer NOT NULL,
    object_name text NOT NULL,
    name character varying(255) NOT NULL,
    type character varying(128),
    created_at timestamptz DEFAULT current_timestamp,
    updated_at timestamptz DEFAULT current_timestamp,
    PRIMARY KEY (file_id),
    UNIQUE (object_name)
);

CREATE TABLE IF NOT EXISTS image_results (
  result_id serial PRIMARY KEY,
  file_id int NOT NULL,
  config_id varchar NOT NULL
);

CREATE TABLE IF NOT EXISTS flowers (
  flower_id serial PRIMARY KEY,
  result_id int NOT NULL,
  class varchar NOT NULL,
  confidence float4 NOT NULL,
  x0 int NOT NULL,
  y0 int NOT NULL,
  x1 int NOT NULL,
  y1 int NOT NULL
);

CREATE TABLE IF NOT EXISTS pollinators (
  pollinator_id serial PRIMARY KEY,
  result_id int NOT NULL,
  flower_id int NOT NULL,
  class varchar NOT NULL,
  confidence float4 NOT NULL,
  x0 int NOT NULL,
  y0 int NOT NULL,
  x1 int NOT NULL,
  y1 int NOT NULL
);

CREATE TABLE IF NOT EXISTS pollinator_inference_config (
  config_id varchar PRIMARY KEY,
  configuration json NOT NULL
);

CREATE TABLE IF NOT EXISTS environment
(
    environment_id serial,
    location point NOT NULL,
    timestamp timestamptz NOT NULL,
    attribute_01 real,
    attribute_02 real,
    attribute_03 real,
    attribute_04 real,
    attribute_05 real,
    attribute_06 real,
    attribute_07 real,
    attribute_08 real,
    attribute_09 real,
    attribute_10 real,
    created_at timestamptz NOT NULL DEFAULT current_timestamp,
    updated_at timestamptz DEFAULT current_timestamp,
    PRIMARY KEY (environment_id)
);

CREATE TABLE IF NOT EXISTS user_collections
(
    user_sub text,
    datasets json,
    UNIQUE (user_sub)
);

CREATE TABLE IF NOT EXISTS annotations
(
    annot_id serial,
    title text NOT NULL,
    user_sub text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT current_timestamp,
    updated_at timestamptz NOT NULL DEFAULT current_timestamp,
    content text,
    url text,
    datasets json,
    PRIMARY KEY (annot_id)
);

-- no foreign key constraints for taxonomy tables
-- data is ever only imported, all taxonomy_tree ids and
-- taxonomy_data.datum_id contain the unique GBIF species_id
-- which may also be used in our own records
CREATE TABLE IF NOT EXISTS taxonomy_tree
(
    species_id bigint,
    genus_id bigint,
    family_id bigint,
    order_id bigint,
    class_id bigint,
    phylum_id bigint,
    kingdom_id bigint NOT NULL,
    CONSTRAINT unique_definition UNIQUE (species_id, genus_id, family_id, order_id, class_id, phylum_id, kingdom_id)
);

CREATE TABLE IF NOT EXISTS taxonomy_data
(
    datum_id bigint NOT NULL,
    label_sci character varying(255) NOT NULL,
    label_de character varying(255),
    label_en character varying(255),
    image_url character varying(255),
    created_at timestamptz NOT NULL DEFAULT current_timestamp,
    updated_at timestamptz NOT NULL DEFAULT current_timestamp,
    PRIMARY KEY (datum_id)
);

CREATE TABLE IF NOT EXISTS walk
(
    walk_id serial,
    title character varying(255),
    description text,
    path double precision[][],
    created_at timestamptz NOT NULL DEFAULT current_timestamp,
    updated_at timestamptz NOT NULL DEFAULT current_timestamp,
    PRIMARY KEY (walk_id)
);

CREATE TABLE IF NOT EXISTS walk_text
(
    text_id serial,
    walk_id int NOT NULL,
    percent_in int NOT NULL,
    percent_out int NOT NULL,
    title character varying(255),
    text character varying(255),
    created_at timestamptz NOT NULL DEFAULT current_timestamp,
    updated_at timestamptz NOT NULL DEFAULT current_timestamp,
    PRIMARY KEY (text_id)
);

CREATE TABLE IF NOT EXISTS walk_hotspot
(
    hotspot_id serial,
    walk_id int NOT NULL,
    location point NOT NULL,
    type integer NOT NULL,
    subject character varying(255),
    data jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT current_timestamp,
    updated_at timestamptz NOT NULL DEFAULT current_timestamp,
    PRIMARY KEY (hotspot_id)
);

CREATE TABLE IF NOT EXISTS storage_whitelist
(
    object_name TEXT,
    PRIMARY KEY (object_name)
);

CREATE TABLE IF NOT EXISTS prod.storage_backend
(
    storage_id serial NOT NULL,
    url_prefix text NOT NULL,
    type character varying(8),
    priority integer NOT NULL DEFAULT 0,
    created_at timestamp with time zone NOT NULL DEFAULT current_timestamp,
    updated_at timestamp with time zone NOT NULL DEFAULT current_timestamp,
    PRIMARY KEY (storage_id),
    UNIQUE (url_prefix)
);

CREATE TABLE IF NOT EXISTS prod.mm_files_audio_storage
(
    file_id integer NOT NULL,
    storage_id integer NOT NULL,
    created_at timestamp with time zone,
    updated_at timestamp with time zone DEFAULT current_timestamp,
    PRIMARY KEY (file_id, storage_id)
);

CREATE TABLE IF NOT EXISTS prod.mm_files_image_storage
(
    file_id integer NOT NULL,
    storage_id integer NOT NULL,
    created_at timestamp with time zone,
    updated_at timestamp with time zone DEFAULT current_timestamp,
    PRIMARY KEY (file_id, storage_id)
);

CREATE TABLE IF NOT EXISTS prod.mm_files_note_storage
(
    file_id integer NOT NULL,
    storage_id integer NOT NULL,
    created_at timestamp with time zone,
    updated_at timestamp with time zone DEFAULT current_timestamp,
    PRIMARY KEY (file_id, storage_id)
);

ALTER TABLE IF EXISTS prod.mm_files_audio_storage
    ADD FOREIGN KEY (file_id)
    REFERENCES prod.files_audio (file_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;

ALTER TABLE IF EXISTS prod.mm_files_audio_storage
    ADD FOREIGN KEY (storage_id)
    REFERENCES prod.storage_backend (storage_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;

ALTER TABLE IF EXISTS prod.mm_files_image_storage
    ADD FOREIGN KEY (file_id)
    REFERENCES prod.files_image (file_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;

ALTER TABLE IF EXISTS prod.mm_files_image_storage
    ADD FOREIGN KEY (storage_id)
    REFERENCES prod.storage_backend (storage_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;

ALTER TABLE IF EXISTS prod.mm_files_note_storage
    ADD FOREIGN KEY (file_id)
    REFERENCES prod.files_note (file_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;

ALTER TABLE IF EXISTS prod.mm_files_note_storage
    ADD FOREIGN KEY (storage_id)
    REFERENCES prod.storage_backend (storage_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;

ALTER TABLE IF EXISTS files_audio
    ADD FOREIGN KEY (deployment_id)
    REFERENCES deployments (deployment_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;

ALTER TABLE IF EXISTS files_image
    ADD FOREIGN KEY (deployment_id)
    REFERENCES deployments (deployment_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;


ALTER TABLE IF EXISTS birdnet_results
    ADD FOREIGN KEY (file_id)
    REFERENCES files_audio (file_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;

ALTER TABLE IF EXISTS birdnet_results
    ADD FOREIGN KEY (task_id)
    REFERENCES birdnet_tasks (task_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;

ALTER TABLE IF EXISTS birdnet_tasks
    ADD FOREIGN KEY (config_id)
    REFERENCES birdnet_configs (config_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE RESTRICT;

ALTER TABLE IF EXISTS birdnet_tasks
    ADD FOREIGN KEY (file_id)
    REFERENCES files_audio (file_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE RESTRICT;

ALTER TABLE IF EXISTS deployments
    ADD FOREIGN KEY (node_id)
    REFERENCES nodes (node_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE RESTRICT;



ALTER TABLE IF EXISTS sensordata_env
    ADD FOREIGN KEY (deployment_id)
    REFERENCES deployments (deployment_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;


ALTER TABLE IF EXISTS sensordata_pax
    ADD FOREIGN KEY (deployment_id)
    REFERENCES deployments (deployment_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;


ALTER TABLE IF EXISTS mm_tags_notes
    ADD FOREIGN KEY (tags_tag_id)
    REFERENCES tags (tag_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE RESTRICT
    NOT VALID;

ALTER TABLE IF EXISTS mm_tags_notes
    ADD FOREIGN KEY (notes_note_id)
    REFERENCES notes (note_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE CASCADE
    NOT VALID;

ALTER TABLE IF EXISTS mm_tags_deployments
    ADD FOREIGN KEY (tags_tag_id)
    REFERENCES tags (tag_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE RESTRICT
    NOT VALID;

ALTER TABLE IF EXISTS mm_tags_deployments
    ADD FOREIGN KEY (deployments_deployment_id)
    REFERENCES deployments (deployment_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE CASCADE
    NOT VALID;

ALTER TABLE IF EXISTS files_note
    ADD FOREIGN KEY (note_id)
    REFERENCES notes (note_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE CASCADE
    NOT VALID;

ALTER TABLE IF EXISTS image_results
  ADD FOREIGN KEY (config_id)
  REFERENCES pollinator_inference_config (config_id) MATCH SIMPLE
  ON UPDATE NO ACTION
  ON DELETE NO ACTION
  NOT VALID;

ALTER TABLE image_results
  ADD CONSTRAINT unique_file_config
  UNIQUE (file_id, config_id);

ALTER TABLE IF EXISTS flowers
  ADD FOREIGN KEY (result_id)
  REFERENCES  image_results  (result_id) MATCH SIMPLE
  ON UPDATE NO ACTION
  ON DELETE NO ACTION
  NOT VALID;

ALTER TABLE IF EXISTS pollinators
  ADD FOREIGN KEY (flower_id)
  REFERENCES  flowers  (flower_id) MATCH SIMPLE
  ON UPDATE NO ACTION
  ON DELETE NO ACTION
  NOT VALID;

ALTER TABLE IF EXISTS image_results
  ADD FOREIGN KEY (file_id)
  REFERENCES  files_image  (file_id) MATCH SIMPLE
  ON UPDATE NO ACTION
  ON DELETE NO ACTION
  NOT VALID;

ALTER TABLE IF EXISTS pollinators
  ADD FOREIGN KEY (result_id)
  REFERENCES  image_results  (result_id) MATCH SIMPLE
  ON UPDATE NO ACTION
  ON DELETE NO ACTION
  NOT VALID;


-- fast delete queries in birdnet_tasks
CREATE INDEX IF NOT EXISTS birdnet_results_tasks_fk_index
    ON birdnet_results USING btree
    (task_id ASC NULLS LAST);

-- fast lookup of duplicates
CREATE INDEX IF NOT EXISTS files_audio_object_name_idx
    ON files_audio USING btree
    (object_name ASC NULLS LAST);

-- fast lookup of duplicates
CREATE INDEX IF NOT EXISTS files_audio_sha256_idx
    ON files_audio USING btree
    (sha256 ASC NULLS LAST);

-- fast lookup of duplicates
CREATE INDEX IF NOT EXISTS files_image_object_name_idx
    ON files_image USING btree
    (object_name ASC NULLS LAST);

-- fast lookup of duplicates
CREATE INDEX IF NOT EXISTS files_image_sha256_idx
    ON files_image USING btree
    (sha256 ASC NULLS LAST);

-- fast lookup of scientific names for joins of taxonomy
CREATE INDEX IF NOT EXISTS taxonomy_data_label_sci_idx
    ON taxonomy_data USING btree
    (label_sci ASC NULLS LAST);

-- fast lookup of whitelist entries
CREATE INDEX IF NOT EXISTS storage_whitelist_object_name_idx
    ON storage_whitelist USING btree
    (object_name ASC NULLS LAST);

CREATE OR REPLACE VIEW birdnet_input
    AS
    SELECT f.file_id,
        f.object_name,
        f.time,
        f.file_size,
        f.sample_rate,
        n.node_label,
        f.duration,
        d.location
      FROM files_audio f
        LEFT JOIN deployments d ON f.deployment_id = d.deployment_id
        LEFT JOIN nodes n ON d.node_id = n.node_id;

CREATE OR REPLACE VIEW birdnet_inferred_species
    AS
    SELECT o.species,
        o.confidence,
        f.time + ((o.time_start || ' seconds')::interval) AS time_start
    FROM birdnet_results o
    LEFT JOIN files_audio f ON o.file_id = f.file_id;

CREATE OR REPLACE VIEW birdnet_inferred_species_day
    AS
    SELECT s.species,
        s.confidence,
        to_char(s.time_start at time zone 'UTC', 'YYYY-mm-DD') AS date
    FROM birdnet_inferred_species s;

CREATE OR REPLACE VIEW birdnet_inferred_species_file_taxonomy
    AS
    SELECT r.species,
        r.confidence,
        d.location,
        f.object_name,
        f.time AS object_time,
        r.time_start AS time_start_relative,
        f.duration AS duration,
        f.time + ((r.time_start || ' seconds')::interval) AS time_start,
        d1.image_url,
        d1.label_de  species_de,
        d1.label_en  species_en,
        d2.label_sci genus,
        d3.label_sci "family",
        d4.label_sci "order",
        d5.label_sci "class",
        d6.label_sci phylum,
        d7.label_sci kingdom

    FROM birdnet_results r

    -- link file information
    LEFT JOIN files_audio     f  ON r.file_id    = f.file_id

    -- link to species label (scientific name in GBIF taxonomy)
    LEFT JOIN taxonomy_data d1 ON r.species    = d1.label_sci

    -- link to species tree (species key to GBIF taxonomy tree)
    LEFT JOIN taxonomy_tree   t  ON d1.datum_id  = t.species_id

    -- link taxonomy tree keys to scientific labels
    LEFT JOIN taxonomy_data d2 ON t.genus_id   = d2.datum_id
    LEFT JOIN taxonomy_data d3 ON t.family_id  = d3.datum_id
    LEFT JOIN taxonomy_data d4 ON t.order_id   = d4.datum_id
    LEFT JOIN taxonomy_data d5 ON t.class_id   = d5.datum_id
    LEFT JOIN taxonomy_data d6 ON t.phylum_id  = d6.datum_id
    LEFT JOIN taxonomy_data d7 ON t.kingdom_id = d7.datum_id

    -- link location data
    LEFT JOIN deployments     d ON f.deployment_id = d.deployment_id

    -- make sure its a species
    WHERE t.species_id IS NOT NULL;

CREATE OR REPLACE VIEW data_records
    AS
    SELECT file_id AS record_id, deployment_id, 'audio' AS type
    FROM files_audio
    UNION
    SELECT file_id AS record_id, deployment_id, 'image' AS type
    FROM files_image;

CREATE SERVER IF NOT EXISTS auth
FOREIGN DATA WRAPPER postgres_fdw
OPTIONS (host 'localhost', dbname 'mitwelten_auth', port '5432');

CREATE USER MAPPING IF NOT EXISTS
FOR mitwelten_internal
SERVER auth
OPTIONS (user 'mw_data_auth_fdw');

CREATE USER MAPPING IF NOT EXISTS
FOR mitwelten_admin
SERVER auth
OPTIONS (user 'mw_data_auth_fdw');

-- this requires the password for the corresponding users to be set
-- see 'schema/README.md#foreign-tables'
IMPORT FOREIGN SCHEMA public LIMIT TO (user_entity)
    FROM SERVER auth INTO "dev";

END;

GRANT USAGE ON SCHEMA "dev" TO
  mitwelten_internal,
  mitwelten_rest,
  mitwelten_public;

GRANT ALL ON ALL TABLES IN SCHEMA "dev" TO mitwelten_internal;
GRANT UPDATE ON ALL SEQUENCES IN SCHEMA "dev" TO mitwelten_internal;

GRANT ALL ON
  nodes,
  sensordata_env,
  sensordata_pax,
  notes,
  tags,
  mm_tags_notes,
  mm_tags_deployments,
  files_note,
  user_collections,
  annotations
TO mitwelten_rest;

GRANT SELECT ON
  birdnet_configs,
  batnet_configs,
  files_audio,
  files_image,
  birdnet_results,
  birdnet_species_occurrence,
  birdnet_tasks
TO mitwelten_rest;

GRANT UPDATE ON
  notes_note_id_seq,
  files_note_file_id_seq,
  nodes_node_id_seq,
  tags_tag_id_seq
TO mitwelten_rest;

GRANT SELECT ON ALL TABLES IN SCHEMA "dev" TO mitwelten_public;
