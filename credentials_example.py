class DbConfig(object):
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

db = DbConfig()
ba = BasicAuth()
oidc = OidcConfig()
minio = MinioConfig()

DEV = False
