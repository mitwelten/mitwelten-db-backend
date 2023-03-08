--
-- Mitwelten Cache Database - Schema V1.0
--

BEGIN;

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

END;

ALTER TABLE IF EXISTS public.gbif
    OWNER TO mw_cache_admin;

GRANT USAGE ON SCHEMA public TO
    mw_cache;

GRANT ALL ON ALL TABLES IN SCHEMA public TO
    mw_cache;
