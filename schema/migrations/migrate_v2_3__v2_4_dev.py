import sys
import psycopg2 as pg
from psycopg2.extras import DictCursor
from psycopg2.extensions import AsIs
import traceback
from tqdm import tqdm

sys.path.append('../../')
import credentials as crd

# If the migration is complete, do not run these migrations again.
MIGRATION_COMPLETE = True

def copy_tags(cursor, SCHEMA_SRC, SCHEMA_DST):
    print('copy tags')
    cursor.execute(f'select * from {SCHEMA_SRC}.tags')
    tags_records_src = cursor.fetchall()
    tags_idmap = {} # tags_idmap src -> dst
    for tr_dst in tqdm(tags_records_src, ascii=True):
        id_src = tr_dst['tag_id']
        cols = list(tr_dst.keys())[1:] # drop id
        vals = tuple(tr_dst[c] for c in cols)
        cursor.execute(f'insert into {SCHEMA_DST}.tags (%s) values %s returning tag_id', (AsIs(','.join(cols)), vals))
        tags_idmap[id_src] = cursor.fetchone()[0]
    return tags_idmap

def copy_entries_to_notes(cursor, SCHEMA_SRC, SCHEMA_DST, user_id):
    print('copy entries to notes')
    cursor.execute(f'select * from {SCHEMA_SRC}.entries')
    entries_records_src = cursor.fetchall()
    notes_idmap = {}
    for er_src in tqdm(entries_records_src, ascii=True):
        id_src = er_src['entry_id']
        cols = 'location, title, description, type, user_sub, public, created_at, updated_at'
        vals = (er_src['location'], er_src['name'], er_src['description'], er_src['type'], user_id, True, er_src['created_at'], er_src['updated_at'])
        cursor.execute(f'insert into {SCHEMA_DST}.notes (%s) values %s returning note_id', (AsIs(cols), vals))
        notes_idmap[id_src] = cursor.fetchone()[0]
    return notes_idmap

def copy_files_entry_to_files_note(cursor, SCHEMA_SRC, SCHEMA_DST, notes_idmap):
    print('copy files_entry to files_note')
    print(SCHEMA_SRC, SCHEMA_DST)
    cursor.execute(f'select * from {SCHEMA_SRC}.files_entry')
    files_entry_records_src = cursor.fetchall()
    for fer_src in tqdm(files_entry_records_src, ascii=True):
        cols = list(fer_src.keys())[1:] # drop id
        vals = list(fer_src[c] for c in cols)
        # replace src entry_id with dst
        eind = cols.index('entry_id')
        cols[eind] = 'note_id'
        vals[eind] = notes_idmap[vals[eind]]
        # replace URL
        on_ind = cols.index('object_name')
        vals[on_ind] = vals[on_ind].replace('https://minio.campusderkuenste.ch/ixdm-mitwelten/viz_app/', '', 1)
        cursor.execute(f'insert into {SCHEMA_DST}.files_note (%s) values %s', (AsIs(','.join(cols)), tuple(vals)))

def migrate_entry_tag_assignment(cursor, SCHEMA_SRC, SCHEMA_DST, tags_idmap, notes_idmap):
    print('copy mm_tags_entries to mm_tags_notes')
    cursor.execute(f'select * from {SCHEMA_SRC}.mm_tags_entries')
    mm_tags_entries_records_src = cursor.fetchall()
    for mmter_src in tqdm(mm_tags_entries_records_src, ascii=True):
        tag_id_dst = tags_idmap[mmter_src['tags_tag_id']]
        # tag_id_dst = mmter_src['tags_tag_id']
        note_id_dst = notes_idmap[mmter_src['entries_entry_id']]
        insert_stmt = f'insert into {SCHEMA_DST}.mm_tags_notes (tags_tag_id, notes_note_id) values (%s, %s)'
        cursor.execute(insert_stmt, (tag_id_dst, note_id_dst))

def truncate_target(pg, SCHEMA_DST):
    print('truncating target...')
    tables = [
        'mm_tags_notes',
        'tags',
        'notes',
        'files_note',
    ]
    c = pg.cursor()
    for t in tables:
        sql = f'TRUNCATE {SCHEMA_DST}.{t} RESTART IDENTITY CASCADE;'
        # uncomment/run only if you know what your doing: All data will be erased!
        c.execute(sql)
        pg.commit()

def check_user_id():
    if len(sys.argv) == 1:
        print('please supply user-id')
        raise Exception('user-id missing, supply KeyCloak user-id for owner of notes records')
    else:
        return sys.argv[1]

def main():
    SCHEMA_SRC = 'prod'
    SCHEMA_DST = 'dev' # WARNING: if set to prod, data may be lost!

    connection = pg.connect(host=crd.db.host,port=crd.db.port,database=crd.db.database,user=crd.db.user,password=crd.db.password)
    cursor = connection.cursor(cursor_factory=DictCursor)

    try:
        user_id = check_user_id()
        truncate_target(connection, SCHEMA_DST)
        tags_idmap = copy_tags(cursor, SCHEMA_SRC, SCHEMA_DST)
        notes_idmap = copy_entries_to_notes(cursor, SCHEMA_SRC, SCHEMA_DST, user_id)
        copy_files_entry_to_files_note(cursor, SCHEMA_SRC, SCHEMA_DST, notes_idmap)
        migrate_entry_tag_assignment(cursor, SCHEMA_SRC, SCHEMA_DST, tags_idmap, notes_idmap)
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
