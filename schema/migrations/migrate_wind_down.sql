-- 2024-11-25

-- -----------------------------------------------------------------------------
-- schema prod

REVOKE ALL ON ALL TABLES IN SCHEMA "prod" FROM mitwelten_public;
REVOKE ALL ON ALL TABLES IN SCHEMA "prod" FROM mitwelten_rest;
REVOKE ALL ON ALL TABLES IN SCHEMA "prod" FROM mitwelten_internal;

GRANT SELECT ON ALL TABLES IN SCHEMA "prod" TO mitwelten_internal;
GRANT SELECT ON ALL TABLES IN SCHEMA "prod" TO mitwelten_public;

-- grant rw access for apps "deploy", "explore" and "discover",
-- and rw access for pax and storage backend
GRANT ALL ON TABLE prod.annotations TO mitwelten_internal;
GRANT ALL ON TABLE prod.deployments TO mitwelten_internal;
GRANT ALL ON TABLE prod.environment TO mitwelten_internal;
GRANT ALL ON TABLE prod.mm_files_audio_storage TO mitwelten_internal;
GRANT ALL ON TABLE prod.mm_files_image_storage TO mitwelten_internal;
GRANT ALL ON TABLE prod.mm_files_note_storage TO mitwelten_internal;
GRANT ALL ON TABLE prod.mm_tags_deployments TO mitwelten_internal;
GRANT ALL ON TABLE prod.mm_tags_notes TO mitwelten_internal;
GRANT ALL ON TABLE prod.nodes TO mitwelten_internal;
GRANT ALL ON TABLE prod.notes TO mitwelten_internal;
GRANT ALL ON TABLE prod.sensordata_pax TO mitwelten_internal;
GRANT ALL ON TABLE prod.storage_backend TO mitwelten_internal;
GRANT ALL ON TABLE prod.storage_whitelist TO mitwelten_internal;
GRANT ALL ON TABLE prod.tags TO mitwelten_internal;
GRANT ALL ON TABLE prod.user_collections TO mitwelten_internal;

REVOKE ALL ON ALL SEQUENCES IN SCHEMA "prod" FROM mitwelten_public;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA "prod" FROM mitwelten_rest;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA "prod" FROM mitwelten_internal;

GRANT ALL ON SEQUENCE prod.annotations_annot_id_seq TO mitwelten_internal;
GRANT ALL ON SEQUENCE prod.deployments_deployment_id_seq TO mitwelten_internal;
GRANT ALL ON SEQUENCE prod.environment_environment_id_seq TO mitwelten_internal;
GRANT ALL ON SEQUENCE prod.nodes_node_id_seq TO mitwelten_internal;
GRANT ALL ON SEQUENCE prod.notes_note_id_seq TO mitwelten_internal;
GRANT ALL ON SEQUENCE prod.files_note_file_id_seq TO mitwelten_internal;
GRANT ALL ON SEQUENCE prod.storage_backend_storage_id_seq TO mitwelten_internal;
GRANT ALL ON SEQUENCE prod.tags_tag_id_seq TO mitwelten_internal;

-- -----------------------------------------------------------------------------
-- schema dev

REVOKE ALL ON ALL TABLES IN SCHEMA "dev" FROM mitwelten_public;
REVOKE ALL ON ALL TABLES IN SCHEMA "dev" FROM mitwelten_rest;
REVOKE ALL ON ALL TABLES IN SCHEMA "dev" FROM mitwelten_internal;

REVOKE ALL ON ALL SEQUENCES IN SCHEMA "dev" FROM mitwelten_public;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA "dev" FROM mitwelten_rest;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA "dev" FROM mitwelten_internal;

REVOKE ALL ON SCHEMA "dev" FROM
  mitwelten_internal,
  mitwelten_rest,
  mitwelten_public;

-- drop all tables in schema dev
do $$ declare
    r record;
begin
    for r in (select tablename from pg_tables where schemaname = 'dev') loop
        execute 'drop table if exists ' || 'dev.' || quote_ident(r.tablename) || ' cascade';
    end loop;
end $$;

-- drop foreign data wrappers
DROP FOREIGN TABLE IF EXISTS dev.user_entity;

