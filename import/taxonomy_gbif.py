import sys
import json
import argparse
import psycopg2 as pg
from pygbif import species as species

sys.path.append('../')
import credentials as crd

keyMap = [ # map db fieldnames to keys in GBIF response
    # for one speciesKey there may exist synonyms in GBIF,
    # prefer the name that matched with the lookup (canonicalName)
    {'db': 'species_id', 'gbif': 'speciesKey' , 'gbif_label': 'canonicalName'},
    {'db': 'genus_id',   'gbif': 'genusKey'   , 'gbif_label': 'genus'},
    {'db': 'family_id',  'gbif': 'familyKey'  , 'gbif_label': 'family'},
    {'db': 'class_id',   'gbif': 'classKey'   , 'gbif_label': 'class'},
    {'db': 'phylum_id',  'gbif': 'phylumKey'  , 'gbif_label': 'phylum'},
    {'db': 'kingdom_id', 'gbif': 'kingdomKey' , 'gbif_label': 'kingdom'}
]
dbfields = ','.join([x['db'] for x in keyMap]) # field definition for sql insert

def fetch_labels(key):
    labels = {}
    offset = 0
    while True:
        # data = species.name_usage(key, language='deu', data='vernacularNames', offset=offset) # 'language' seens to be ignored
        data = species.name_usage(key, data='vernacularNames', offset=offset)
        de = [x for x in data['results'] if x['language'] == 'deu']
        en = [x for x in data['results'] if x['language'] == 'eng']
        if len(de) and 'de' not in labels: labels['de'] = de[0]['vernacularName']
        if len(en) and 'en' not in labels: labels['en'] = en[0]['vernacularName']
        if data['endOfRecords'] or len(labels) == 2: break
        else: offset += 100
    return labels

def main():
    parser = argparse.ArgumentParser(description='Import taxonomy for inferred species from GBIF')
    args = parser.parse_args()

    connection = pg.connect(host=crd.db.host,port=crd.db.port,database=crd.db.database,user=crd.db.user,password=crd.db.password)
    cursor = connection.cursor()

    # query all species from db (inferred by birdnet)
    cursor.execute('select species from prod.birdnet_results group by species')
    splist = cursor.fetchall()
    splist = [x[0] for x in splist]
    print(f'Compiled list of {len(splist)} inferred species in db')

    # query taxonomy info from gbif
    # - check if info is complete in db
    # - if not pull from gbif
    print('fetching taxonomy for all birdnet inferred species in db')
    species_data = [ species.name_backbone(x) for x in splist]

    for taxon in species_data:
        print('parsing', taxon['canonicalName'])
        # check if label record exist in db, query and insert if not
        for k in keyMap:
            cursor.execute('select * from prod.taxonomy_labels where label_id = %s', (taxon[k['gbif']],))
            label = cursor.fetchall()
            if not len(label):
                # query
                labels = fetch_labels(taxon[k['gbif']])
                # insert
                cursor.execute('insert into prod.taxonomy_labels (label_id, label_sci, label_de, label_en) values (%s,%s,%s,%s)',
                    (taxon[k['gbif']], taxon[k['gbif_label']], labels.get('de'), labels.get('en')))
            else: break # if the label exists, the parents exist, too
        cursor.execute(f'insert into prod.taxonomy_species ({dbfields}) values (%s,%s,%s,%s,%s,%s) on conflict do nothing',
            tuple((taxon[k] for k in [x['gbif'] for x in keyMap])))
        connection.commit()

if __name__ == '__main__':
    main()
