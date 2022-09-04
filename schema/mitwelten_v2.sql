--
-- Mitwelten Database - Schema V2.1
--

BEGIN;

CREATE SCHEMA IF NOT EXISTS prod
    AUTHORIZATION mitwelten_admin;

CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE IF NOT EXISTS prod.birdnet_configs
(
    config_id serial,
    config jsonb NOT NULL,
    comment text,
    created_at timestamptz NOT NULL DEFAULT current_timestamp,
    updated_at timestamptz NOT NULL DEFAULT current_timestamp,
    PRIMARY KEY (config_id),
    UNIQUE (config)
);

CREATE TABLE IF NOT EXISTS prod.files_audio
(
    file_id serial,
    object_name text NOT NULL,
    sha256 character varying(64) NOT NULL,
    time timestamptz NOT NULL,
    deployment_id integer NOT NULL,
    duration double precision NOT NULL,
    serial_number character varying(32),
    format character varying(64),
    file_size integer NOT NULL,
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

CREATE TABLE IF NOT EXISTS prod.files_image
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

CREATE TABLE IF NOT EXISTS prod.birdnet_results
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

CREATE TABLE IF NOT EXISTS prod.birdnet_species_occurrence
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

CREATE TABLE IF NOT EXISTS prod.birdnet_tasks
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

CREATE TABLE IF NOT EXISTS prod.nodes
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

CREATE TABLE IF NOT EXISTS prod.deployments
(
    deployment_id serial,
    node_id integer NOT NULL,
    location point NOT NULL,
    description text,
    period tstzrange NOT NULL DEFAULT tstzrange('-infinity', 'infinity'),
    PRIMARY KEY (deployment_id),
    EXCLUDE USING GIST (node_id WITH =, period WITH &&)
);

CREATE TABLE IF NOT EXISTS prod.sensordata_env
(
    time timestamptz NOT NULL,
    deployment_id integer NOT NULL,
    temperature double precision,
    humidity double precision,
    moisture double precision,
    voltage real
);

CREATE TABLE IF NOT EXISTS prod.sensordata_pax
(
    time timestamptz NOT NULL,
    deployment_id integer NOT NULL,
    pax integer NOT NULL,
    voltage real
);

CREATE TABLE IF NOT EXISTS prod.entries
(
    entry_id serial,
    location point NOT NULL,
    name character varying(255),
    description text,
    type character varying(255),
    created_at timestamptz NOT NULL DEFAULT current_timestamp,
    updated_at timestamptz NOT NULL DEFAULT current_timestamp,
    PRIMARY KEY (entry_id)
);

CREATE TABLE IF NOT EXISTS prod.tags
(
    tag_id serial,
    name character varying(255) NOT NULL,
    created_at timestamptz DEFAULT current_timestamp,
    updated_at timestamptz DEFAULT current_timestamp,
    PRIMARY KEY (tag_id),
    UNIQUE (name)
);

CREATE TABLE IF NOT EXISTS prod.mm_tags_entries
(
    tags_tag_id integer,
    entries_entry_id integer,
    PRIMARY KEY (tags_tag_id, entries_entry_id)
);

CREATE TABLE IF NOT EXISTS prod.mm_tags_deployments
(
    tags_tag_id integer,
    deployments_deployment_id integer,
    PRIMARY KEY (tags_tag_id, deployments_deployment_id)
);

CREATE TABLE IF NOT EXISTS prod.files_entry
(
    file_id serial,
    entry_id integer NOT NULL,
    object_name text NOT NULL,
    name character varying(255) NOT NULL,
    type character varying(128),
    created_at timestamptz DEFAULT current_timestamp,
    updated_at timestamptz DEFAULT current_timestamp,
    PRIMARY KEY (file_id),
    UNIQUE (object_name)
);

ALTER TABLE IF EXISTS prod.files_audio
    ADD FOREIGN KEY (deployment_id)
    REFERENCES prod.deployments (deployment_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;

ALTER TABLE IF EXISTS prod.files_image
    ADD FOREIGN KEY (deployment_id)
    REFERENCES prod.deployments (deployment_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;


ALTER TABLE IF EXISTS prod.birdnet_results
    ADD FOREIGN KEY (file_id)
    REFERENCES prod.files_audio (file_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;

ALTER TABLE IF EXISTS prod.birdnet_results
    ADD FOREIGN KEY (task_id)
    REFERENCES prod.birdnet_tasks (task_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;

ALTER TABLE IF EXISTS prod.birdnet_tasks
    ADD FOREIGN KEY (config_id)
    REFERENCES prod.birdnet_configs (config_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE RESTRICT;

ALTER TABLE IF EXISTS prod.birdnet_tasks
    ADD FOREIGN KEY (file_id)
    REFERENCES prod.files_audio (file_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE RESTRICT;

ALTER TABLE IF EXISTS prod.deployments
    ADD FOREIGN KEY (node_id)
    REFERENCES prod.nodes (node_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE RESTRICT;



ALTER TABLE IF EXISTS prod.sensordata_env
    ADD FOREIGN KEY (deployment_id)
    REFERENCES prod.deployments (deployment_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;


ALTER TABLE IF EXISTS prod.sensordata_pax
    ADD FOREIGN KEY (deployment_id)
    REFERENCES prod.deployments (deployment_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;


ALTER TABLE IF EXISTS prod.mm_tags_entries
    ADD FOREIGN KEY (tags_tag_id)
    REFERENCES prod.tags (tag_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;

ALTER TABLE IF EXISTS prod.mm_tags_entries
    ADD FOREIGN KEY (entries_entry_id)
    REFERENCES prod.entries (entry_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;

ALTER TABLE IF EXISTS prod.mm_tags_deployments
    ADD FOREIGN KEY (tags_tag_id)
    REFERENCES prod.tags (tag_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;

ALTER TABLE IF EXISTS prod.mm_tags_deployments
    ADD FOREIGN KEY (deployments_deployment_id)
    REFERENCES prod.deployments (deployment_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;

ALTER TABLE IF EXISTS prod.files_entry
    ADD FOREIGN KEY (entry_id)
    REFERENCES prod.entries (entry_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE CASCADE
    NOT VALID;

-- fast delete queries in birdnet_tasks
CREATE INDEX IF NOT EXISTS birdnet_results_tasks_fk_index
    ON prod.birdnet_results USING btree
    (task_id ASC NULLS LAST);

-- fast lookup of duplicates
CREATE INDEX IF NOT EXISTS files_audio_object_name_idx
    ON prod.files_audio USING btree
    (object_name ASC NULLS LAST);

-- fast lookup of duplicates
CREATE INDEX IF NOT EXISTS files_audio_sha256_idx
    ON prod.files_audio USING btree
    (sha256 ASC NULLS LAST);

-- fast lookup of duplicates
CREATE INDEX IF NOT EXISTS files_image_object_name_idx
    ON prod.files_image USING btree
    (object_name ASC NULLS LAST);

-- fast lookup of duplicates
CREATE INDEX IF NOT EXISTS files_image_sha256_idx
    ON prod.files_image USING btree
    (sha256 ASC NULLS LAST);


CREATE OR REPLACE VIEW prod.birdnet_input
    AS
    SELECT f.file_id,
        f.object_name,
        f.time,
        f.file_size,
        f.sample_rate,
        n.node_label,
        f.duration,
        d.location
      FROM prod.files_audio f
        LEFT JOIN prod.deployments d ON f.deployment_id = d.deployment_id
        LEFT JOIN prod.nodes n ON d.node_id = n.node_id;

CREATE OR REPLACE VIEW prod.birdnet_inferred_species
    AS
    SELECT o.species,
        o.confidence,
        f.time + ((o.time_start || ' seconds')::interval) AS time_start
    FROM prod.birdnet_results o
    LEFT JOIN prod.files_audio f ON o.file_id = f.file_id;

CREATE OR REPLACE VIEW prod.birdnet_inferred_species_day
    AS
    SELECT s.species,
        s.confidence,
        to_char(s.time_start at time zone 'UTC', 'YYYY-mm-DD') AS date
    FROM prod.birdnet_inferred_species s;

CREATE OR REPLACE VIEW prod.data_records
    AS
    SELECT file_id AS record_id, deployment_id, 'audio' AS type
    FROM prod.files_audio
    UNION
    SELECT file_id AS record_id, deployment_id, 'image' AS type
    FROM prod.files_image;

END;

GRANT USAGE ON SCHEMA prod TO  mitwelten_internal, mitwelten_rest, mitwelten_upload, mitwelten_public;

GRANT ALL ON ALL TABLES IN SCHEMA prod TO mitwelten_internal;
GRANT UPDATE ON ALL SEQUENCES IN SCHEMA prod TO mitwelten_internal;

GRANT ALL ON prod.nodes, prod.sensordata_env, prod.sensordata_pax, prod.entries, prod.tags, prod.mm_tags_entries, prod.mm_tags_deployments, prod.files_entry TO mitwelten_rest;
GRANT SELECT ON prod.birdnet_configs, prod.files_audio, prod.files_image, prod.birdnet_results, prod.birdnet_species_occurrence, prod.birdnet_tasks TO mitwelten_rest;
GRANT UPDATE ON prod.entries_entry_id_seq, prod.files_entry_file_id_seq, prod.nodes_node_id_seq, prod.tags_tag_id_seq TO mitwelten_rest;

GRANT ALL ON prod.files_audio, prod.files_image, prod.nodes TO mitwelten_upload;
GRANT UPDATE ON prod.files_audio_file_id_seq, prod.files_image_file_id_seq, prod.nodes_node_id_seq TO mitwelten_upload;

GRANT SELECT ON ALL TABLES IN SCHEMA prod TO mitwelten_public;
