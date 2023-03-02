from api.database import database
from api.dependencies import check_authentication, crd
from api.routers import (
    birdnet, data, deployments, geo, entries, ingest, nodes, queue, tags,
    taxonomy, validators
)

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

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
        'name': 'inferrence',
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
        'name': 'entries',
        'description': 'Pins, added to the map',
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
        'name': 'files',
        'description': 'Files uploaded for / added to entries',
    },
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
        ],
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
)

app.include_router(birdnet.router)
app.include_router(data.router)
app.include_router(deployments.router)
app.include_router(entries.router)
app.include_router(geo.router)
app.include_router(ingest.router)
app.include_router(nodes.router)
app.include_router(queue.router)
app.include_router(tags.router)
app.include_router(taxonomy.router)
app.include_router(validators.router)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    exc_str = f'{exc}'.replace('\n', ' ').replace('   ', ' ')
    print(f"{request}: {exc_str}")
    content = {'status_code': 10422, 'message': exc_str, 'data': None}
    return JSONResponse(content=content, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

@app.on_event('startup')
async def startup():
    await database.connect()

@app.on_event('shutdown')
async def shutdown():
    await database.disconnect()

@app.get('/login', tags=['authentication'])
def login(login_state: bool = Depends(check_authentication)):
    return login_state

@app.get('/', include_in_schema=False)
async def root():
    return { 'name': 'Mitwelten Data API', 'version': '3.0' }
