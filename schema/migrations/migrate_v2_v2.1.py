import sys
import json
import psycopg2 as pg
from psycopg2.extras import DictCursor, execute_values
from psycopg2.extensions import AsIs
from tqdm import tqdm

sys.path.append('../../')
import credentials as crd

connection = pg.connect(host=crd.db.host,port=crd.db.port,database=crd.db.database,user=crd.db.user,password=crd.db.password)
cursor = connection.cursor(cursor_factory=DictCursor)

# needs db admin on localhost
print('truncating target')
tables = [
    'deployments',
    'mm_tags_entries',
    'mm_tags_deployments',
    'tags',
    'nodes',
    'entries',
    'birdnet_configs',
    'birdnet_results',
    'birdnet_tasks',
    'files_audio',
    'files_image',
    'files_entry',
    'sensordata_env',
    'sensordata_pax',
    'birdnet_species_occurrence',
]
for t in tables:
    cursor.execute(f'truncate prod.{t} restart identity cascade')
    connection.commit()

# insert / migrate node tags
print('migrating dev.tags')
cursor.execute('select * from dev.tags')
tags_records_dev = cursor.fetchall()
tags_idmap = {} # tags_idmap dev -> prod
for trd in tqdm(tags_records_dev, ascii=True):
    id_dev = trd['tag_id']
    cols = list(trd.keys())[1:] # drop id
    vals = tuple(trd[c] for c in cols)
    cursor.execute(f'insert into prod.tags (%s) values %s returning tag_id', (AsIs(','.join(cols)), vals))
    tags_idmap[id_dev] = cursor.fetchone()[0]


# migrate nodes, create id-mapping
print('migrating dev.nodes')
cursor.execute('select * from dev.nodes')
nodes_records_dev = cursor.fetchall()
nodes_idmap = {} # nodes_idmap dev -> prod
for nrd in tqdm(nodes_records_dev, ascii=True):
    id_dev = nrd['node_id']
    cols = list(nrd.keys())[1:] # drop id
    vals = tuple(nrd[c] for c in cols)
    cursor.execute(f'insert into prod.nodes (%s) values %s returning node_id', (AsIs(','.join(cols)), vals))
    nodes_idmap[id_dev] = cursor.fetchone()[0]


# locations
print('creating id-mapping for dev.locations')
cursor.execute('select * from dev.locations')
locations_records_dev = cursor.fetchall()
locations_dev = {r['location_id']:r for r in locations_records_dev}


# deployments
print('migrating dev.deployments, integrating dev.locations into prod.deployments')
cursor.execute('select * from dev.deployments')
deployments_records_dev = cursor.fetchall()
deployments_idmap = {} # deployments_idmap dev -> prod
for drd in tqdm(deployments_records_dev, ascii=True):
    id_dev = drd['deployment_id']

    node_id_prod = nodes_idmap[drd['node_id']]
    location_dev = locations_dev[drd['location_id']]
    location_prod = location_dev['location']
    # string concat: locations.description (locations.type)
    description_prod = []
    if location_dev['description'] != None: description_prod.append(location_dev['description'])
    if location_dev['type'] != None: description_prod.append(f"({location_dev['type']})")
    description_prod = ' '.join(description_prod)
    period_prod = drd['period']

    cursor.execute('insert into prod.deployments (node_id, location, description, period) values %s returning deployment_id',
        ((node_id_prod, location_prod, description_prod, period_prod),))
    id_prod = cursor.fetchone()[0]
    deployments_idmap[id_dev] = id_prod

    # INSERT TAG and MM for location names
    if location_dev['name'] != None:
        # - check if tag exists
        cursor.execute('select tag_id from prod.tags where name = %s', (location_dev['name'],))
        tag_return_prod = cursor.fetchone()
        # - if not, insert
        if tag_return_prod == None:
            cursor.execute('insert into prod.tags (name) values (%s) returning tag_id', (location_dev['name'],))
            tag_return_prod = cursor.fetchone()
        tag_id_prod = tag_return_prod[0]
        # - insert mm record
        cursor.execute('insert into prod.mm_tags_deployments (tags_tag_id, deployments_deployment_id) values %s', ((tag_id_prod, id_prod),))


# migrate node - tag assignment to deployment - tag assignment,
# tagging the newer deployment if multiple match,
# only cam nodes for FS2 had been tagged so far
print('migrating dev.mm_tags_nodes to prod.mm_tags_deployments')
cursor.execute('select * from dev.mm_tags_nodes')
mm_tags_nodes_records_dev = cursor.fetchall()
for mmtdr in tqdm(mm_tags_nodes_records_dev, ascii=True):
    tag_id_prod = tags_idmap[mmtdr['tags_tag_id']]
    node_id_prod = nodes_idmap[mmtdr['nodes_node_id']]
    # deployments_deployment_id <- nodes_node_id
    insert_stmt = '''
    insert into prod.mm_tags_deployments (tags_tag_id, deployments_deployment_id)
    values (%s, (select deployment_id from prod.deployments where node_id = %s order by period desc limit 1))
    '''
    cursor.execute(insert_stmt, (tag_id_prod, node_id_prod))


# entries
print('migrating dev.entries, integrating dev.locations into prod.entries')
cursor.execute('select * from dev.entries')
entries_records_dev = cursor.fetchall()
entries_idmap = {}
for erd in tqdm(entries_records_dev, ascii=True):
    id_dev = erd['entry_id']
    cols = list(erd.keys())[1:] # drop id
    vals = list(erd[c] for c in cols)
    # replace field 'location_id' with 'location'
    lind = cols.index('location_id')
    vals[lind] = locations_dev[vals[lind]]['location']
    cols[lind] = 'location'
    cursor.execute(f'insert into prod.entries (%s) values %s returning entry_id', (AsIs(','.join(cols)), tuple(vals)))
    entries_idmap[id_dev] = cursor.fetchone()[0]


# files_entry
print('migrating dev.files_entry')
cursor.execute('select * from dev.files_entry')
files_entry_records_dev = cursor.fetchall()
files_entry_idmap = {}
for ferd in tqdm(files_entry_records_dev, ascii=True):
    id_dev = ferd['file_id']
    cols = list(ferd.keys())[1:] # drop id
    vals = list(ferd[c] for c in cols)
    # replace dev entry_id with prod
    eind = cols.index('entry_id')
    vals[eind] = entries_idmap[vals[eind]]
    cursor.execute(f'insert into prod.files_entry (%s) values %s', (AsIs(','.join(cols)), tuple(vals)))


# migrate entry - tag assignment
print('migrating dev.mm_tags_entries')
cursor.execute('select * from dev.mm_tags_entries')
mm_tags_entries_records_dev = cursor.fetchall()
for mmetrd in tqdm(mm_tags_entries_records_dev, ascii=True):
    tag_id_prod = tags_idmap[mmetrd['tags_tag_id']]
    entry_id_prod = entries_idmap[mmetrd['entries_entry_id']]
    insert_stmt = 'insert into prod.mm_tags_entries (tags_tag_id, entries_entry_id) values (%s, %s)'
    cursor.execute(insert_stmt, (tag_id_prod, entry_id_prod))


# birdnet_configs
# using a better method with `execute_values`
print('migrating dev.birdnet_configs')
cursor.execute('select * from dev.birdnet_configs')
configs_records_dev = cursor.fetchall()
if len(configs_records_dev) > 0:
    configs = []
    configs_id_dev = []
    configs_idmap = {}
    for config in configs_records_dev:
        config['config'] = json.dumps(config['config'], indent=None, skipkeys=True)
        configs_id_dev.append(config['config_id'])
        configs.append(tuple(config[1:]))
    cols = list(configs_records_dev[0].keys())
    configs_id_prod = execute_values(cursor, f'insert into prod.birdnet_configs ({",".join(cols[1:])}) values %s returning config_id', configs, fetch=True)
    configs_idmap = {cm[0]:cm[1] for cm in zip(configs_id_dev, [c[0] for c in configs_id_prod])}


# birdnet_species_occurrence
print('copying dev.birdnet_species_occurrence')
cursor.execute('insert into prod.birdnet_species_occurrence (select * from dev.birdnet_species_occurrence)')

print('committing...')
connection.commit()

# files_audio
# - set deployment id from 'select deployment_id from prod.deployments where node_id = %s and files_audio.time <@ period
# use server side cursor for tables with many records
print('migrating dev.files_audio, with related records of dev.birdnet_tasks and dev.birdnet_results')
cursor.execute('select count(file_id) from dev.files_audio')
pbar = tqdm(total=cursor.fetchone()[0], ascii=True)
cursor_exp = connection.cursor(cursor_factory=DictCursor, name='export_dev')
cursor_exp.execute('select * from dev.files_audio')
while True:
    records = cursor_exp.fetchmany(size=2000)
    if len(records) == 0:
        break
    for record in records:
        # insert file, replacing node_id,location_id with deployment_id
        file_id_dev = record['file_id']
        file_cols = list(record.keys())[1:] # drop id
        file_cols.remove('node_id')
        file_cols.remove('location_id')
        file_vals = tuple(record[c] for c in file_cols)
        file_cols.append('deployment_id')

        insert_stmt = f'''
        insert into prod.files_audio ({",".join(file_cols)})
        values ({"%s,"*len(file_vals)} (select deployment_id from prod.deployments where node_id = %s and %s <@ period))
        returning file_id
        '''
        cursor.execute(insert_stmt, tuple([*file_vals, nodes_idmap[record['node_id']], record['time']]))
        file_id_prod = cursor.fetchone()[0]

        # lookup tasks referencing the file
        cursor.execute('select task_id, config_id, batch_id, state, scheduled_on, pickup_on, end_on from dev.birdnet_tasks where file_id = %s', (file_id_dev,))
        for task in cursor.fetchall():
            task_id_dev = task['task_id']
            # insert tasks (-> file_id)
            cursor.execute('insert into prod.birdnet_tasks (file_id, config_id, batch_id, state, scheduled_on, pickup_on, end_on) values %s returning task_id',
                (tuple([file_id_prod, configs_idmap[task['config_id']], *task[2:]]),))
            task_id_prod = cursor.fetchone()[0]
            # lookup results referencing tasks
            cursor.execute('select time_start, time_end, confidence, species from dev.birdnet_results where task_id = %s', (task_id_dev,))
            results_prod = []
            for result in cursor.fetchall():
                results_prod.append(tuple([task_id_prod, file_id_prod, *result]))
            # insert results (-> task_id, file_id)
            execute_values(cursor, 'insert into prod.birdnet_results (task_id, file_id, time_start, time_end, confidence, species) values %s', results_prod)
        pbar.update(1)
pbar.close()
cursor_exp.close()
print('committing...')
connection.commit()


# files_image
print('migrating dev.files_image')
cursor.execute('select count(file_id) from dev.files_image')
pbar = tqdm(total=cursor.fetchone()[0], ascii=True)
cursor_exp = connection.cursor(cursor_factory=DictCursor, name='export_dev')
cursor_exp.execute('''select object_name, sha256, time,
    (select deployment_id from dev.deployments d where d.node_id = f.node_id and f.time <@ period) as deployment_id, file_size, resolution, created_at, updated_at
from dev.files_image f
''')
while True:
    files_image_records_dev = cursor_exp.fetchmany(size=5000)
    if len(files_image_records_dev) == 0:
        break
    cols_files_image = list(files_image_records_dev[0].keys())
    files = []
    for record in files_image_records_dev:
        record['deployment_id'] = deployments_idmap[record['deployment_id']]
        files.append(tuple(record))
    execute_values(cursor, f'insert into prod.files_image ({",".join(cols_files_image)}) values %s', files)
    pbar.update(len(files))
pbar.close()
cursor_exp.close()


# sensordata_env
print('migrating dev.sensordata_env')
cursor.execute('select count(time) from dev.sensordata_env')
cursor.execute('''select time, temperature, humidity, moisture, voltage,
    (select deployment_id from dev.deployments d where d.node_id = se.node_id and se.time <@ period) as deployment_id
from dev.sensordata_env se
''')
sensordata_env_records_dev = cursor.fetchall()
cols_sensordata_env = list(sensordata_env_records_dev[0].keys())
sensordata = []
for record in sensordata_env_records_dev:
    record['deployment_id'] = deployments_idmap[record['deployment_id']]
    sensordata.append(tuple(record))
execute_values(cursor, f'insert into prod.sensordata_env ({",".join(cols_sensordata_env)}) values %s', sensordata)


# sensordata_pax
print('migrating dev.sensordata_pax')
cursor.execute('select count(time) from dev.sensordata_pax')
cursor.execute('''select time, pax, voltage,
    (select deployment_id from dev.deployments d where d.node_id = sp.node_id and sp.time <@ period) as deployment_id
from dev.sensordata_pax sp
''')
sensordata_pax_records_dev = cursor.fetchall()
cols_sensordata_pax = list(sensordata_pax_records_dev[0].keys())
sensordata = []
for record in sensordata_pax_records_dev:
    record['deployment_id'] = deployments_idmap[record['deployment_id']]
    sensordata.append(tuple(record))
execute_values(cursor, f'insert into prod.sensordata_pax ({",".join(cols_sensordata_pax)}) values %s', sensordata)


print('committing...')
connection.commit()

print('checking record counts')
for t in tables:
    td = 'mm_tags_nodes' if t == 'mm_tags_deployments' else t
    cursor.execute(f'select (select count(0) from dev.{td}) as dev, (select count(0) from prod.{t}) as prod')
    d,p = cursor.fetchone()
    msg = '' if d == p else '!!!'
    print(f'{msg}[{d}/{p}]\tdev.{td} -> prod.{t}')

print('integrity check for files_audio')
cursor.execute('''
select object_name, node_label, regexp_replace(object_name, '(\\d{4}-\\d{4}|AM(?:1|2))/.*', '\\1') as label_check
from dev.files_audio f left join dev.nodes n on n.node_id = f.node_id
''')
mismatch_count = 0
for cmp in tqdm(cursor.fetchall()):
    try:
        if cmp[2] == 'AM1': assert cmp[1] == '7758-4041'
        elif cmp[2] == 'AM2': assert cmp[1] == '7257-5673'
        else: assert cmp[2] == cmp[1]
    except AssertionError:
        mismatch_count += 1
        print(list(cmp))
print('files_audio: object_name / node_label mismatch count:', mismatch_count)

cursor.close()
connection.close()
