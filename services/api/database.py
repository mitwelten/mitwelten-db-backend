import databases

from api.config import crd

database = databases.Database(
    databases.DatabaseURL('postgresql://'),
    host=crd.db.host,
    port=crd.db.port,
    user=crd.db.user,
    password=crd.db.password,
    database=crd.db.database,
    min_size=5,
    max_size=10
)

database_cache = databases.Database(
    databases.DatabaseURL('postgresql://'),
    host=crd.db_cache.host,
    port=crd.db_cache.port,
    user=crd.db_cache.user,
    password=crd.db_cache.password,
    database=crd.db_cache.database,
    min_size=5,
    max_size=10
)
