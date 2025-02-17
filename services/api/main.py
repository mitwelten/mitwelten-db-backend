from api.database import database, database_cache
from api.dependencies import crd
from api.routers import (
    birdnet, data, deployments, discover, geo, notes, ingest, minio, nodes, queue, tags,
    taxonomy, validators, walk, meteodata, pollinators, explore, gbif,
    environment, statistics, auth, tv
)

from fastapi import Depends, FastAPI, Request, status
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from redis import asyncio as aioredis

tags_metadata = [
    {
        'name': 'authentication',
        'description': 'Handle authentication',
    },
    {
        'name': 'deployments',
        'description': 'Node deployments management',
    },
    {
        'name': 'explore',
        'description': 'API routes for explore.mitwelten.org',
    },
    {
        'name': 'inference',
        'description': 'Machine-Learning inference results',
    },
    {
        'name': 'taxonomy',
        'description': 'Look-up of taxonomy keywords / relationships',
    },
    {
        'name': 'queue',
        'description': 'Machine-Learning queue monitoring and management',
    },
    {
        'name': 'kml',
        'description': 'Layers for map display',
    },
    {
        'name': 'notes',
        'description': 'Notes, may be added to the map',
    },
    {
        'name': 'nodes',
        'description': 'Data collection devices',
    },
    {
        'name': 'tags',
        'description': 'Tags',
    },
    {
        'name': 'data',
        'description': 'Sensor / Capture Data',
    },
    {
        'name': 'storage',
        'description': 'File up- and download (images, audio, etc.)',
    },
    {
        'name': 'meteodata',
        'description': 'Meteodata from external sources',
    },
    {
        'name': 'pollinator',
        'description': 'Pollinator study results',
    },
    {
        'name': 'gbif',
        'description': 'GBIF Occurrences',
    },
    {
        'name': 'environment',
        'description': 'Environment Characteristics',
    },
    {
        'name': 'statistics',
        'description': 'Statistics for image and audio files by deployment',
    }
]

app = FastAPI(
    title='Mitwelten Data API',
    description='This service provides REST endpoints to exchange data from [Mitwelten](https://mitwelten.org)',
    contact={'email': 'mitwelten.technik@fhnw.ch'},
    version='3.0.0',
    openapi_tags=tags_metadata,
    servers=[
        {'url': 'https://data.mitwelten.org/api/v3', 'description': 'Production environment'},
        {'url': 'http://localhost:8000', 'description': 'Development environment'}
    ],
    root_path='/api/v3',
    root_path_in_servers=False,
    # dependencies=[Depends(check_authentication)]
)

if crd.DEV == True:
    from fastapi.middleware.cors import CORSMiddleware
    app.root_path = '/'
    app.root_path_in_servers=True
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            'http://localhost',              # dev environment
            'http://localhost:4200',         # angular dev environment
            'http://localhost:8000',         # dash dev environment
        ],
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
)

app.include_router(auth.router)
app.include_router(birdnet.router)
app.include_router(data.router)
app.include_router(deployments.router)
app.include_router(discover.router)
app.include_router(notes.router)
app.include_router(geo.router)
app.include_router(ingest.router)
app.include_router(minio.router)
app.include_router(nodes.router)
app.include_router(queue.router)
app.include_router(tags.router)
app.include_router(taxonomy.router)
app.include_router(validators.router)
app.include_router(walk.router)
app.include_router(tv.router)
app.include_router(meteodata.router)
app.include_router(pollinators.router)
app.include_router(explore.router)
app.include_router(gbif.router)
app.include_router(environment.router)
app.include_router(statistics.router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    exc_str = f'{exc}'.replace('\n', ' ').replace('   ', ' ')
    print(f'{request}: {exc_str}')
    content = {'status_code': 10422, 'message': exc_str, 'data': None}
    return JSONResponse(content=content, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

@app.on_event('startup')
async def startup():
    await database.connect()
    await database_cache.connect()
    redis = RedisBackend(aioredis.from_url('redis://redis_cache'))
    FastAPICache.init(backend=redis, prefix='fastapi-cache')

@app.on_event('shutdown')
async def shutdown():
    await database.disconnect()
    await database_cache.disconnect()

@app.get('/', include_in_schema=False)
async def root():
    return { 'name': 'Mitwelten Data API', 'version': '3.0' }
