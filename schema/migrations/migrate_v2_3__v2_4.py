import sys
import psycopg2 as pg
from psycopg2.extras import DictCursor
from tqdm import tqdm
import traceback

from migrate_v2_3__v2_4_dev import check_user_id, copy_files_entry_to_files_note, copy_entries_to_notes

sys.path.append('../../')
import credentials as crd

# If the migration is complete, do not run these migrations again.
MIGRATION_COMPLETE = False

def migrate_entry_tag_assignment(cursor, SCHEMA_SRC, SCHEMA_DST, notes_idmap):
    print('copy mm_tags_entries to mm_tags_notes')
    cursor.execute(f'select * from {SCHEMA_SRC}.mm_tags_entries')
    mm_tags_entries_records_src = cursor.fetchall()
    for mmter_src in tqdm(mm_tags_entries_records_src, ascii=True):
        tag_id_dst = mmter_src['tags_tag_id'] # same
        note_id_dst = notes_idmap[mmter_src['entries_entry_id']]
        insert_stmt = f'insert into {SCHEMA_DST}.mm_tags_notes (tags_tag_id, notes_note_id) values (%s, %s)'
        cursor.execute(insert_stmt, (tag_id_dst, note_id_dst))

def create_new_tables(pg, SCHEMA_DST):
    sql = f'''
    SET SEARCH_PATH = "{SCHEMA_DST}";

    DROP TABLE IF EXISTS mm_tags_notes, files_note, notes RESTRICT;
    DROP SEQUENCE IF EXISTS notes_note_id_seq, files_note_file_id_seq RESTRICT;

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

    CREATE TABLE IF NOT EXISTS mm_tags_notes
    (
        tags_tag_id integer,
        notes_note_id integer,
        PRIMARY KEY (tags_tag_id, notes_note_id)
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

    ALTER TABLE IF EXISTS mm_tags_notes
        ADD FOREIGN KEY (tags_tag_id)
        REFERENCES tags (tag_id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE NO ACTION
        NOT VALID;

    ALTER TABLE IF EXISTS mm_tags_notes
        ADD FOREIGN KEY (notes_note_id)
        REFERENCES notes (note_id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE CASCADE
        NOT VALID;

    ALTER TABLE IF EXISTS files_note
        ADD FOREIGN KEY (note_id)
        REFERENCES notes (note_id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE CASCADE
        NOT VALID;

    GRANT ALL ON ALL TABLES IN SCHEMA "{SCHEMA_DST}" TO mitwelten_internal;
    GRANT UPDATE ON ALL SEQUENCES IN SCHEMA "{SCHEMA_DST}" TO mitwelten_internal;

    GRANT ALL ON
    notes,
    mm_tags_notes,
    files_note
    TO mitwelten_rest;

    GRANT UPDATE ON
    notes_note_id_seq,
    files_note_file_id_seq
    TO mitwelten_rest;

    GRANT SELECT ON ALL TABLES IN SCHEMA "{SCHEMA_DST}" TO mitwelten_public;
    '''
    c = pg.cursor()
    c.execute(sql)
    pg.commit()

def drop_old_tables(pg, SCHEMA_SRC):
    sql = f'''
    SET SEARCH_PATH = "{SCHEMA_SRC}";
    DROP TABLE IF EXISTS mm_tags_entries, files_entry, entries RESTRICT;
    DROP SEQUENCE IF EXISTS entries_entry_id_seq, files_entry_file_id_seq RESTRICT;
    '''
    print('please drop tables manually:')
    print(sql)
    # c = pg.cursor()
    # c.execute(sql)
    # pg.commit()

def main():
    SCHEMA_SRC = 'prod'
    SCHEMA_DST = SCHEMA_SRC

    connection = pg.connect(host=crd.db.host,port=crd.db.port,database=crd.db.database,user=crd.db.user,password=crd.db.password)
    cursor = connection.cursor(cursor_factory=DictCursor)

    try:
        user_id = check_user_id()
        create_new_tables(connection, SCHEMA_DST)
        notes_idmap = copy_entries_to_notes(cursor, SCHEMA_SRC, SCHEMA_DST, user_id)
        copy_files_entry_to_files_note(cursor, SCHEMA_SRC, SCHEMA_DST, notes_idmap)
        migrate_entry_tag_assignment(cursor, SCHEMA_SRC, SCHEMA_DST, notes_idmap)
        drop_old_tables(connection, SCHEMA_SRC)
    except:
        print(traceback.format_exc())
        print('rolling back...')
        connection.rollback()
    else:
        print('committing...')
        connection.commit()


if __name__ == '__main__':

    if MIGRATION_COMPLETE:
        print('not running migrations')
        sys.exit(1)

    main()
