class DbConfig(object):
    host = 'localhost'
    port = 5432
    database = 'db'
    schema = 'public'
    user = 'postgres'
    password = 'secret'

class CacheDbConfig(object):
    host = 'localhost'
    port = 5432
    database = 'db'
    schema = 'public'
    user = 'postgres'
    password = 'secret'

class BasicAuth(object):
    url = 'http://localhost:8080'
    username = 'username'
    password = 'password'

class OidcConfig(object):
    KC_SERVER_URL = 'https://identityprovider.tld/auth/'
    KC_CLIENT_ID = 'client_id'
    KC_REALM_NAME = 'realm'
    KC_CLIENT_SECRET = 'secret'

class MinioConfig(object):
    host = ''
    bucket = ''
    access_key = ''
    secret_key = ''

class MinioConfigScaled(MinioConfig):
    '''Scaled images'''
    host = ''
    bucket = ''

class MinioConfigWeb(MinioConfig):
    '''Web content'''
    host = ''
    bucket = ''

db = DbConfig()
db_cache = CacheDbConfig()
ba = BasicAuth()
oidc = OidcConfig()
minio = MinioConfig()
minio_scaled = MinioConfigScaled()
minio_web = MinioConfigWeb()

DEV = False
