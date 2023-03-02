from typing import List

from api.database import database
from api.models import Taxon
from api.tables import taxonomy_data, taxonomy_tree

from fastapi import APIRouter
from sqlalchemy.sql import select, text

router = APIRouter()

# ------------------------------------------------------------------------------
# TAXONOMY LOOKUP
# ------------------------------------------------------------------------------

@router.get('/taxonomy/id/{identifier}', response_model=List[Taxon],
    summary='Taxonomy lookup by numeric identifier (GBIF key)',
    description='Lookup taxonomy of a given numeric __GBIF key__, returning the taxon tree with translated labels',
    tags=['taxonomy'])
async def taxonomy_by_id(identifier: int) -> List[Taxon]:
    keyMap = [ # map db fieldnames to keys in GBIF response
        # for one species there may exist subspecies in GBIF,
        # referred to by a usage key, which is used here as identifier in 'species_id'
        {'db': 'species_id', 'gbif': 'usageKey',   'gbif_label': 'scientificName', 'rank': 'SUBSPECIES'},
        # for one speciesKey there may exist synonyms in GBIF,
        # prefer the name that matched with the lookup (canonicalName)
        {'db': 'species_id', 'gbif': 'speciesKey', 'gbif_label': 'canonicalName',  'rank': 'SPECIES'},
        {'db': 'genus_id',   'gbif': 'genusKey',   'gbif_label': 'genus',          'rank': 'GENUS'},
        {'db': 'family_id',  'gbif': 'familyKey',  'gbif_label': 'family',         'rank': 'FAMILY'},
        {'db': 'class_id',   'gbif': 'classKey',   'gbif_label': 'class',          'rank': 'CLASS'},
        {'db': 'phylum_id',  'gbif': 'phylumKey',  'gbif_label': 'phylum',         'rank': 'PHYLUM'},
        {'db': 'kingdom_id', 'gbif': 'kingdomKey', 'gbif_label': 'kingdom',        'rank': 'KINGDOM'}
    ]
    # lookup tree
    tree_columns = ','.join(taxonomy_tree.c.keys())
    query = select(taxonomy_tree).where(text(f':identifier IN ({tree_columns})').bindparams(identifier=identifier)).limit(1)
    tree = await database.fetch_one(query)
    tree = [tree._mapping[k['db']] for k in keyMap[1:]]
    # filter tree until id matches
    tree_offset = tree.index(identifier)
    # query data for remaining ids
    data_query = select(taxonomy_data).where(taxonomy_data.c.datum_id.in_(tuple(tree[tree_offset:])))
    data = await database.fetch_all(data_query)
    data = {datum['datum_id']: datum for datum in data}
    # return array of tree, with rank info added
    return [{**dict(data[t]), 'rank': keyMap[tree_offset+i+1]['rank']} for i,t in enumerate(tree[tree_offset:])]

@router.get('/taxonomy/sci/{identifier}', response_model=List[Taxon],
    summary='Taxonomy lookup by scientific identifier',
    description='Lookup taxonomy of a given __scientific identifier__, returning the taxon tree with translated labels',
    tags=['taxonomy'])
async def taxonomy_by_sci(identifier: str) -> List[Taxon]:
    query = select(taxonomy_data.c.datum_id).where(taxonomy_data.c.label_sci == identifier)
    result = await database.fetch_one(query)
    return await taxonomy_by_id(result['datum_id'])
