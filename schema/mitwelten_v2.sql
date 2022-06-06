BEGIN;

CREATE SCHEMA IF NOT EXISTS dev
    AUTHORIZATION mitwelten_admin;

CREATE TABLE IF NOT EXISTS dev.birdnet_configs
(
    config_id serial,
    config jsonb NOT NULL,
    comment text,
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
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (file_id)
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
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (file_id),
    UNIQUE (object_name),
    UNIQUE (sha256)
);

CREATE TABLE IF NOT EXISTS dev.birdnet_results
(
    result_id serial,
    task_id integer NOT NULL,
    file_id integer NOT NULL,
    object_name text NOT NULL, -- remove?
    time_start real NOT NULL,
    time_end real NOT NULL,
    confidence real NOT NULL,
    species character varying(255) NOT NULL,
    PRIMARY KEY (result_id)
);

CREATE TABLE IF NOT EXISTS dev.species_occurrence
(
    id serial,
    species character varying(255) NOT NULL,
    occurence integer,
    unlikely boolean,
    comment text,
    PRIMARY KEY (id),
    UNIQUE (species)
);

CREATE TABLE IF NOT EXISTS dev.birdnet_tasks
(
    task_id serial,
    file_id integer NOT NULL,
    config_id integer NOT NULL,
    state integer NOT NULL,
    scheduled_on timestamptz NOT NULL,
    pickup_on timestamptz,
    end_on timestamptz,
    PRIMARY KEY (task_id)
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
    ADD CONSTRAINT tasks_file_id_fkey FOREIGN KEY (file_id)
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

END;

GRANT ALL ON ALL TABLES IN SCHEMA dev TO mitwelten_internal;
GRANT UPDATE ON ALL SEQUENCES IN SCHEMA dev TO mitwelten_internal;

GRANT ALL ON dev.files_audio, dev.files_image TO mitwelten_upload;
GRANT UPDATE ON dev.files_audio_file_id_seq,  dev.files_image_file_id_seq TO mitwelten_upload;

GRANT SELECT ON ALL TABLES IN SCHEMA dev TO mitwelten_public;
