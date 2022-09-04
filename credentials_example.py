class DbConfig(object):
  host = 'localhost'
  port = 5432
  database = 'db'
  user = 'postgres'
  password = 'secret'

class BasicAuth(object):
    username = 'username'
    password = 'password'

db = DbConfig()
ba = BasicAuth()

DEV = False
