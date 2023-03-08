import simplekml

from api.database import database
from api.tables import deployments, nodes

from fastapi import APIRouter, Response
from sqlalchemy.sql import LABEL_STYLE_TABLENAME_PLUS_COL, select, text

router = APIRouter(tags=['kml'])

# ------------------------------------------------------------------------------
# GEO DATA (KML export)
# ------------------------------------------------------------------------------

@router.get('/kml/{fs}/', tags=['kml'], response_class=Response(media_type="application/vnd.google-earth.kml+xml"))
async def read_kml(fs: str):
    query = deployments.select()

    query = select(deployments.alias('d').outerjoin(nodes.alias('n'))).\
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
        p.coords = [(d['location']['lon'],d['location']['lat'],0)]
        # p.tessellate = True

    return Response(content=kml.kml(format=True), media_type="application/vnd.google-earth.kml+xml")
