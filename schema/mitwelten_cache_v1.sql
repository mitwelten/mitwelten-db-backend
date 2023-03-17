--
-- Mitwelten Cache Database - Schema V1.0
--

BEGIN;

CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS public.gbif
(
    "key" bigint,
    eventDate timestamptz,
    decimalLongitude real,
    decimalLatitude real,
    --
    taxonKey bigint,
    kingdomKey bigint,
    phylumKey bigint,
    classKey bigint,
    orderKey bigint,
    familyKey bigint,
    genusKey bigint,
    speciesKey bigint,
    --
    "references" character varying(255),
    gbifReference character varying(255),
    --
    datasetKey character varying(255),
    datasetName character varying(255),
    datasetReference character varying(255),
    license character varying(255),
    --
    basisOfRecord character varying(255),
    --
    mediaType character varying(255),
    media jsonb,
    PRIMARY KEY ("key")
);

CREATE TABLE public.station (
    station_id TEXT NOT NULL,
    station_name TEXT NOT NULL,
    data_src TEXT NOT NULL,
    location point NOT NULL,
    altitude integer,
    PRIMARY KEY (station_id)

);

CREATE TABLE public.parameter (
    param_id TEXT NOT NULL,
    unit TEXT NOT NULL,
    description TEXT,
    PRIMARY KEY (param_id)
);

CREATE TABLE public.meteodata (
    ts timestamptz NOT NULL,
    param_id TEXT REFERENCES parameter(param_id),
    station_id TEXT REFERENCES station(station_id),
    value double precision NOT NULL,
    UNIQUE (ts, param_id, station_id)
);

SELECT create_hypertable('meteodata', 'ts');

CREATE INDEX meteodata_station_id_idx
ON public.meteodata (station_id, ts DESC);

CREATE INDEX meteodata_param_id_idx
ON public.meteodata (param_id, ts DESC);


END;

ALTER TABLE IF EXISTS public.gbif
    OWNER TO mw_cache_admin;

ALTER TABLE IF EXISTS public.station
    OWNER TO mw_cache_admin;

ALTER TABLE IF EXISTS public.parameter
    OWNER TO mw_cache_admin;

ALTER TABLE IF EXISTS public.meteodata
    OWNER TO mw_cache_admin;

GRANT USAGE ON SCHEMA public TO
    mw_cache;

GRANT ALL ON ALL TABLES IN SCHEMA public TO
    mw_cache;
