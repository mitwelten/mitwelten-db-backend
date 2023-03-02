import databases

from api.config import crd

DATABASE_URL = f'postgresql://{crd.db.user}:{crd.db.password}@{crd.db.host}:{crd.db.port}/{crd.db.database}'
database = databases.Database(DATABASE_URL, min_size=5, max_size=10)
