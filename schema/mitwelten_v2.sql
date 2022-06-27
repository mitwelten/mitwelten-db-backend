BEGIN;

CREATE SCHEMA IF NOT EXISTS dev
    AUTHORIZATION mitwelten_admin;

CREATE TABLE IF NOT EXISTS dev.birdnet_configs
(
    config_id serial,
    config jsonb NOT NULL,
    comment text,
    created_at timestamptz NOT NULL DEFAULT current_timestamp,
    updated_at timestamptz NOT NULL DEFAULT current_timestamp,
    PRIMARY KEY (config_id),
    UNIQUE (config)
);

CREATE TABLE IF NOT EXISTS dev.files_audio
(
    file_id serial,
    object_name text NOT NULL,
    sha256 character varying(64) NOT NULL,
    time timestamptz NOT NULL,
    node_id integer NOT NULL,
    location_id integer,
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

CREATE TABLE IF NOT EXISTS dev.files_image
(
    file_id serial,
    object_name text NOT NULL,
    sha256 character varying(64) NOT NULL,
    time timestamptz NOT NULL,
    node_id integer NOT NULL,
    location_id integer,
    file_size integer NOT NULL,
    resolution integer[] NOT NULL,
    created_at timestamptz NOT NULL DEFAULT current_timestamp,
    updated_at timestamptz NOT NULL DEFAULT current_timestamp,
    PRIMARY KEY (file_id),
    UNIQUE (object_name),
    UNIQUE (sha256)
);

CREATE TABLE IF NOT EXISTS dev.birdnet_results
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

CREATE TABLE IF NOT EXISTS dev.birdnet_species_occurrence
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

CREATE TABLE IF NOT EXISTS dev.birdnet_tasks
(
    task_id serial,
    file_id integer NOT NULL,
    config_id integer NOT NULL,
    batch_id integer NOT NULL,
    state integer NOT NULL,
    scheduled_on timestamptz NOT NULL,
    pickup_on timestamptz,
    end_on timestamptz,
    PRIMARY KEY (task_id),
    CONSTRAINT unique_task_in_batch UNIQUE (file_id, config_id, batch_id)
);

CREATE TABLE IF NOT EXISTS dev.locations
(
    location_id serial,
    location point NOT NULL,
    type character varying(128),
    name character varying(128),
    description text,
    PRIMARY KEY (location_id),
    UNIQUE (name)
);

CREATE TABLE IF NOT EXISTS dev.nodes
(
    node_id serial,
    node_label character varying(32) NOT NULL,
    type character varying(128) NOT NULL,
    serial_number character varying(128),
    description text,
    PRIMARY KEY (node_id),
    UNIQUE (node_label)
);

CREATE TABLE IF NOT EXISTS dev.sensordata_env
(
    time timestamptz NOT NULL,
    node_id integer NOT NULL,
    location_id integer NOT NULL,
    temperature double precision NOT NULL,
    humidity double precision NOT NULL,
    moisture double precision NOT NULL,
    voltage real
);

CREATE TABLE IF NOT EXISTS dev.sensordata_pax
(
    time timestamptz NOT NULL,
    node_id integer NOT NULL,
    location_id integer NOT NULL,
    pax integer NOT NULL,
    voltage real
);

CREATE TABLE IF NOT EXISTS dev.entries
(
    entry_id serial,
    location_id integer NOT NULL,
    name character varying(255),
    description text,
    type character varying(255),
    created_at timestamptz NOT NULL DEFAULT current_timestamp,
    updated_at timestamptz NOT NULL DEFAULT current_timestamp,
    PRIMARY KEY (entry_id)
    -- UNIQUE (entry_id, location_id, name)
);

CREATE TABLE IF NOT EXISTS dev.tags
(
    tag_id serial,
    name character varying(255) NOT NULL,
    created_at timestamptz DEFAULT current_timestamp,
    updated_at timestamptz DEFAULT current_timestamp,
    PRIMARY KEY (tag_id)
);

CREATE TABLE IF NOT EXISTS dev.mm_tags_entries
(
    tags_tag_id integer,
    entries_entry_id integer,
    PRIMARY KEY (tags_tag_id, entries_entry_id)
);

CREATE TABLE IF NOT EXISTS dev.mm_tags_nodes
(
    tags_tag_id integer,
    nodes_node_id integer,
    PRIMARY KEY (tags_tag_id, nodes_node_id)
);

CREATE TABLE IF NOT EXISTS dev.files_entry
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

ALTER TABLE IF EXISTS dev.files_audio
    ADD FOREIGN KEY (location_id)
    REFERENCES dev.locations (location_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;

ALTER TABLE IF EXISTS dev.files_audio
    ADD FOREIGN KEY (node_id)
    REFERENCES dev.nodes (node_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;

ALTER TABLE IF EXISTS dev.files_image
    ADD FOREIGN KEY (location_id)
    REFERENCES dev.locations (location_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;

ALTER TABLE IF EXISTS dev.files_image
    ADD FOREIGN KEY (node_id)
    REFERENCES dev.nodes (node_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;

ALTER TABLE IF EXISTS dev.birdnet_results
    ADD FOREIGN KEY (file_id)
    REFERENCES dev.files_audio (file_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;

ALTER TABLE IF EXISTS dev.birdnet_results
    ADD FOREIGN KEY (task_id)
    REFERENCES dev.birdnet_tasks (task_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;

ALTER TABLE IF EXISTS dev.birdnet_tasks
    ADD FOREIGN KEY (config_id)
    REFERENCES dev.birdnet_configs (config_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE RESTRICT;

ALTER TABLE IF EXISTS dev.birdnet_tasks
    ADD FOREIGN KEY (file_id)
    REFERENCES dev.files_audio (file_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE RESTRICT;

ALTER TABLE IF EXISTS dev.sensordata_env
    ADD FOREIGN KEY (node_id)
    REFERENCES dev.nodes (node_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;

ALTER TABLE IF EXISTS dev.sensordata_env
    ADD FOREIGN KEY (location_id)
    REFERENCES dev.locations (location_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;

ALTER TABLE IF EXISTS dev.sensordata_pax
    ADD FOREIGN KEY (node_id)
    REFERENCES dev.nodes (node_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;

ALTER TABLE IF EXISTS dev.sensordata_pax
    ADD FOREIGN KEY (location_id)
    REFERENCES dev.locations (location_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;

ALTER TABLE IF EXISTS dev.entries
    ADD FOREIGN KEY (location_id)
    REFERENCES dev.locations (location_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;

ALTER TABLE IF EXISTS dev.mm_tags_entries
    ADD FOREIGN KEY (tags_tag_id)
    REFERENCES dev.tags (tag_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;

ALTER TABLE IF EXISTS dev.mm_tags_entries
    ADD FOREIGN KEY (entries_entry_id)
    REFERENCES dev.entries (entry_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;

ALTER TABLE IF EXISTS dev.mm_tags_nodes
    ADD FOREIGN KEY (tags_tag_id)
    REFERENCES dev.tags (tag_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;

ALTER TABLE IF EXISTS dev.mm_tags_nodes
    ADD FOREIGN KEY (nodes_node_id)
    REFERENCES dev.nodes (node_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;

ALTER TABLE IF EXISTS dev.files_entry
    ADD FOREIGN KEY (entry_id)
    REFERENCES dev.entries (entry_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;

-- fast delete queries in birdnet_tasks
CREATE INDEX IF NOT EXISTS birdnet_results_tasks_fk_index
    ON dev.birdnet_results USING btree
    (task_id ASC NULLS LAST);

-- fast lookup of duplicates
CREATE INDEX IF NOT EXISTS files_audio_object_name_idx
    ON dev.files_audio USING btree
    (object_name ASC NULLS LAST);

-- fast lookup of duplicates
CREATE INDEX IF NOT EXISTS files_audio_sha256_idx
    ON dev.files_audio USING btree
    (sha256 ASC NULLS LAST);

-- fast lookup of duplicates
CREATE INDEX IF NOT EXISTS files_image_object_name_idx
    ON dev.files_image USING btree
    (object_name ASC NULLS LAST);

-- fast lookup of duplicates
CREATE INDEX IF NOT EXISTS files_image_sha256_idx
    ON dev.files_image USING btree
    (sha256 ASC NULLS LAST);


CREATE OR REPLACE VIEW dev.birdnet_input
    AS
    SELECT f.file_id,
        f.object_name,
        f.time,
        f.file_size,
        f.sample_rate,
        n.node_label,
        f.duration,
        l.location
      FROM dev.files_audio f
        LEFT JOIN dev.nodes n ON f.node_id = n.node_id
        LEFT JOIN dev.locations l ON f.location_id = l.location_id;

CREATE OR REPLACE VIEW dev.birdnet_inferred_species
    AS
    SELECT o.species,
        o.confidence,
        f.time + ((o.time_start || ' seconds')::interval) AS time_start
    FROM dev.birdnet_results o
    LEFT JOIN dev.files_audio f ON o.file_id = f.file_id;

CREATE OR REPLACE VIEW dev.birdnet_inferred_species_day
    AS
    SELECT s.species,
        s.confidence,
        to_char(s.time_start at time zone 'UTC', 'YYYY-mm-DD') AS date
    FROM dev.birdnet_inferred_species s;

CREATE OR REPLACE VIEW dev.entries_location
    AS
    SELECT e.*, l.location
    FROM dev.entries e
    LEFT JOIN dev.locations l ON e.location_id = l.location_id;

CREATE OR REPLACE VIEW dev.data_records
    AS
    SELECT file_id AS record_id, node_id, location_id, 'audio' AS type
    FROM dev.files_audio
    UNION
    SELECT file_id AS record_id, node_id, location_id, 'image' AS type
    FROM dev.files_image;

END;

GRANT USAGE ON SCHEMA dev TO  mitwelten_internal, mitwelten_rest, mitwelten_upload, mitwelten_public;

GRANT ALL ON ALL TABLES IN SCHEMA dev TO mitwelten_internal;
GRANT UPDATE ON ALL SEQUENCES IN SCHEMA dev TO mitwelten_internal;

GRANT ALL ON dev.locations, dev.nodes, dev.sensordata_env, dev.sensordata_pax, dev.entries, dev.tags, dev.mm_tags_entries, dev.mm_tags_nodes, dev.files_entry TO mitwelten_rest;
GRANT SELECT ON dev.birdnet_configs, dev.files_audio, dev.files_image, dev.birdnet_results, dev.birdnet_species_occurrence, dev.birdnet_tasks TO mitwelten_rest;
GRANT UPDATE ON dev.entries_entry_id_seq, dev.files_entry_file_id_seq, dev.locations_location_id_seq, dev.nodes_node_id_seq, dev.tags_tag_id_seq TO mitwelten_rest;

GRANT ALL ON dev.files_audio, dev.files_image, dev.nodes TO mitwelten_upload;
GRANT UPDATE ON dev.files_audio_file_id_seq, dev.files_image_file_id_seq, dev.nodes_node_id_seq TO mitwelten_upload;

GRANT SELECT ON ALL TABLES IN SCHEMA dev TO mitwelten_public;
