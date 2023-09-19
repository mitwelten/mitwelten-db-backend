import sys
import psycopg2 as pg
from psycopg2.extras import DictCursor
from tqdm import tqdm
import traceback

from migrate_v2_3__v2_4_dev import check_user_id, copy_files_entry_to_files_note, copy_entries_to_notes

sys.path.append('../../')
import credentials as crd

SCHEMA_DST = 'prod'
SCHEMA_SRC = 'prod'

# If the migration is complete, do not run these migrations again.
MIGRATION_COMPLETE = True

def migrate_entry_tag_assignment(cursor, notes_idmap):
    print('copy mm_tags_entries to mm_tags_notes')
    cursor.execute(f'select * from {SCHEMA_SRC}.mm_tags_entries')
    mm_tags_entries_records_src = cursor.fetchall()
    for mmter_src in tqdm(mm_tags_entries_records_src, ascii=True):
        tag_id_dst = mmter_src['tags_tag_id'] # same
        note_id_dst = notes_idmap[mmter_src['entries_entry_id']]
        insert_stmt = f'insert into {SCHEMA_DST}.mm_tags_notes (tags_tag_id, notes_note_id) values (%s, %s)'
        cursor.execute(insert_stmt, (tag_id_dst, note_id_dst))

if __name__ == '__main__':

    if MIGRATION_COMPLETE:
        print('not running migrations')
        sys.exit(1)

    connection = pg.connect(host=crd.db.host,port=crd.db.port,database=crd.db.database,user=crd.db.user,password=crd.db.password)
    cursor = connection.cursor(cursor_factory=DictCursor)

    try:
        user_id = check_user_id()
        notes_idmap = copy_entries_to_notes(cursor, user_id)
        copy_files_entry_to_files_note(cursor, notes_idmap)
        migrate_entry_tag_assignment(cursor, notes_idmap)
    except:
        print(traceback.format_exc())
        print('rolling back...')
        connection.rollback()
    else:
        if not MIGRATION_COMPLETE:
            print('committing...')
            connection.commit()
