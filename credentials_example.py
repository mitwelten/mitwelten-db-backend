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

db = DbConfig()
ba = BasicAuth()

DEV = False
