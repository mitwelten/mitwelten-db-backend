import sys
import databases

import sqlalchemy
from sqlalchemy.sql import select, text, LABEL_STYLE_TABLENAME_PLUS_COL

from fastapi import FastAPI, Response

import simplekml

from tables import nodes, locations, deployments

sys.path.append('../../')
import credentials as crd

DATABASE_URL = f'postgresql://{crd.db.user}:{crd.db.password}@{crd.db.host}/{crd.db.database}'
database = databases.Database(DATABASE_URL)
engine = sqlalchemy.create_engine(DATABASE_URL)

tags_metadata = [
    {
        'name': 'kml',
        'description': 'Layers for map display',
    },
]

app = FastAPI(
    title='Mitwelten GEO REST API',
    description='This service provides REST endpoints to exchange geo data from [Mitwelten](https://mitwelten.org)',
    contact={'email': 'mitwelten.technik@fhnw.ch'},
    version='1.0.0',
    openapi_tags=tags_metadata,
    servers=[
        {'url': 'https://data.mitwelten.org/geo/v1', 'description': 'Production environment'},
        {'url': 'http://localhost:8000', 'description': 'Development environment'}
    ],
    root_path='/geo/v1',
    root_path_in_servers=False
)

@app.on_event('startup')
async def startup():
    await database.connect()

@app.on_event('shutdown')
async def shutdown():
    await database.disconnect()


@app.get('/kml/{fs}/', tags=['kml'])
async def read_kml(fs: str):
    query = deployments.select()

    query = select(deployments.alias('d').outerjoin(nodes.alias('n')).outerjoin(locations.alias('l'))).\
        set_label_style(LABEL_STYLE_TABLENAME_PLUS_COL)

    # if object_type != None:
    #     query = query.where(text('n.type = :node_type').bindparams(node_id=object_type))

    if fs == 'fs2':
        query = query.where(text("d.period && tstzrange('2022-01-01 00:00:00+01','2023-01-01 00:00:00+01')"))
    elif fs == 'fs1':
        query = query.where(text("d.period && tstzrange('2021-01-01 00:00:00+01','2022-01-01 00:00:00+01')"))

    result = await database.fetch_all(query)

    records = []
    for r in result:
        d = { c: r['d_'+c] for c in deployments.columns.keys() }
        d['location'] = { c: r['l_'+c] for c in locations.columns.keys() }
        d['node'] = { c: r['n_'+c] for c in nodes.columns.keys() }
        records.append(d)

    kml = simplekml.Kml(name='Mitwelten Nodes')
    ext = simplekml.ExtendedData()
    ext.newdata('type', 'marker')

    style = simplekml.Style()
    style.iconstyle.hotspot = simplekml.HotSpot(x = 24, y = 4.8, xunits='pixels', yunits='pixels')
    style.iconstyle.icon = simplekml.Icon(gxw = 48, gxh = 48)
    style.iconstyle.icon.href = 'https://api3.geo.admin.ch/color/255,0,0/marker-24@2x.png'
    style.labelstyle.color = simplekml.Color.red

    for d in records:
        p = kml.newpoint()
        p.style = style
        p.name = d['node']['node_label']
        p.description = f"{d['node']['platform']} ({d['node']['type']})"
        p.extendeddata = ext
        p.altitudemode = simplekml.AltitudeMode.clamptoground
        p.coords = [(d['location']['location']['lon'],d['location']['location']['lat'],0)]
        # p.tessellate = True

    return Response(content=kml.kml(format=True), media_type="application/vnd.google-earth.kml+xml")


@app.get('/', include_in_schema=False)
async def root():
    return {'message': 'Mitwelten GEO REST service'}
