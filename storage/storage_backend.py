import os
import traceback
from dataclasses import dataclass
from typing import Union
from urllib.parse import urlparse

import psycopg2 as pg
from jinja2 import Environment, FileSystemLoader
from minio import Minio

from config import LocalStorageDefaults, crd

@dataclass
class S3Storage:
    type: str = 's3'
    storage: Minio
    host: str
    bucket: str

    def __repr__(self):
        return f"S3Storage(type={self.type}, host={self.host}, bucket={self.bucket})"

@dataclass
class LocalStorage:
    type: str = 'local'
    path: str

    def __repr__(self):
        return f"LocalStorage(type={self.type}, path={self.path})"

def parse_kv_file(file_path):
    kv_dict = {}
    with open(file_path, 'r') as f:
        for line in f:
            key, value = line.strip().split('=', 1)
            kv_dict[key] = value
    return kv_dict

def check_s3_storage(backend) -> S3Storage:
    url_prefix = backend[1]
    parsed_url = urlparse(url_prefix)
    minio_host = parsed_url.netloc
    minio_bucket = parsed_url.path.strip('/')

    storage = Minio(
        minio_host,
        access_key=crd.minio.access_key,
        secret_key=crd.minio.secret_key,
    )
    if not storage.bucket_exists(minio_bucket):
        raise ValueError(f'Bucket {minio_bucket} does not exist.')
    else:
        print(f'Bucket {minio_bucket} on {minio_host} exists.')

    return S3Storage(storage=storage, host=minio_host, bucket=minio_bucket)

def check_local_storage(backend) -> LocalStorage:

    url_prefix = backend[1]
    # test if the backend is accessible
    while True:
        if not os.path.exists(url_prefix):
            print(f"URL prefix {url_prefix} does not exist.")
            # ask the user to input the path to the storage device or directory
            url_prefix = input("Enter the path to the storage device or directory: ")
            if len(url_prefix) == 0:
                print('exiting')
                return
        else: break

    # test if the backend is writable
    if not os.access(url_prefix, os.W_OK):
        print(f"URL prefix {url_prefix} is not writable.")
        return

    # read the dot-file to identify the storage device
    lsd = LocalStorageDefaults()
    backend_properties = parse_kv_file(os.path.join(url_prefix, lsd.dot_file_name))

    # test if backend_properties match the backend storage record
    if backend_properties['storage_id'] != str(backend[0]):
        print(f"Storage ID in dot-file does not match backend storage record.")
        return
    if backend_properties['device_label'] != str(backend[-1]):
        print(f"Device label in dot-file does not match notes in backend storage record.")
        return
    if backend_properties['created_at'] != str(backend[4]):
        print(f"Creation date in dot-file does not match creation date in backend storage record.")
        return

    abs_storage_dir = os.path.join(url_prefix, backend_properties['storage_dir'])
    if not os.access(abs_storage_dir, os.W_OK):
        print(f"backend {abs_storage_dir} is not writable.")
        return

    return LocalStorage(path=abs_storage_dir)

def get_storage_backend(backend_id: int) -> Union[S3Storage, LocalStorage]:
    with pg.connect(host=crd.db.host, port=crd.db.port, database=crd.db.database, user=crd.db.user, password=crd.db.password) as connection:
        with connection.cursor() as cursor:
            cursor.execute('select * from prod.storage_backend where storage_id = %s', (backend_id,))
            backend = cursor.fetchone()

    if not backend:
        raise ValueError(f'No storage backend with id {backend_id} found.')

    if str(backend[2]).lower() == 's3':
        return check_s3_storage(backend)
    elif str(backend[2]).lower() == 'local':
        return check_local_storage(backend)

def create_local_storage_backend(path, priority, notes):
    '''
    Add records to the storage_backend table to create a new storage backend.

    If the storage backend to be added is a physical device, add a dot-file to identify it, i.e. .mitwelten-storage-id
    To add a physical device , use the option --type=local and the path to the directory containing the dot-file.

    This will create:

    1. a record in the storage_backend table with the url_prefix set to the path to the directory
    2. a dot-file in the directory to identify it as a storage backend
    3. README.md file in the directory with instructions on how to use the storage backend
    4. a subdirectory "archive" in the directory to store archived files
    '''

    lsd = LocalStorageDefaults()
    lsd.priority = priority
    lsd.device_label = notes.strip().replace('\n', ',')[:128]

    # Check if the directories and files already exist
    try:
        if os.path.exists(path[0]):
            print(f'[OK] Directory {path[0]} exists.')
            lsd.original_path = path[0]
        else:
            raise Exception(f'Directory {path[0]} does not exist.')

        dot_file_path = os.path.join(lsd.original_path, lsd.dot_file_name)
        if os.path.exists(dot_file_path):
            raise Exception(f'Dot-file {dot_file_path} already exists.')

        readme_file_path = os.path.join(lsd.original_path, 'README.md')
        if os.path.exists(readme_file_path):
            raise Exception(f'{readme_file_path} already exists.')

        archive_dir = os.path.join(lsd.original_path, lsd.storage_dir)
        if os.path.exists(archive_dir):
            raise Exception(f'Archive directory {archive_dir} already exists.')

    except:
        print(traceback.format_exc())
        return

    try:
        # Create a record in the storage_backend table
        # with the url_prefix set to the path to the directory
        connection = pg.connect(host=crd.db.host, port=crd.db.port, database=crd.db.database, user=crd.db.user, password=crd.db.password)
        with connection.cursor() as cursor:
            cursor.execute('''
                INSERT INTO prod.storage_backend (url_prefix, type, priority, notes)
                VALUES (%s, %s, %s, %s)
                RETURNING storage_id, created_at
                ;
            ''', (lsd.original_path, type, lsd.priority, lsd.device_label))
            insert_data = cursor.fetchone()
            lsd.storage_id = insert_data[0] # integer
            lsd.created_at = insert_data[1] # datetime object

        if not lsd.storage_id:
            raise Exception(f'Failed to create record in storage_backend table.')

        # Create a dot-file in the target directory to identify it as a storage backend
        with open(dot_file_path, 'w') as file:
            properties = [
                f'storage_id={lsd.storage_id}',
                f'created_at={lsd.created_at}',
                f'storage_dir={lsd.storage_dir}',
                f'url_prefix={lsd.original_path}',
                f'device_label={lsd.device_label}',
            ]
            file.write('\n'.join(properties) + '\n')

        # Render the README template
        env = Environment(loader=FileSystemLoader('.'))
        template = env.get_template('README.md.j2')
        template_data = dict(**vars(lsd))
        template_data['frontmatter'] = '\n'.join({f'{k}: {v}' for k,v in template_data.items()})
        template_data['created_at'] = lsd.created_at.strftime('%Y-%m-%d %H:%M:%S')
        readme = template.render(template_data)
        with open(readme_file_path, 'w') as file:
            file.write(readme)

        # Create the subdirectory that will hold the archived files
        archive_dir = os.path.join(path[0], 'archive')
        os.makedirs(archive_dir)

    except Exception as e:
        connection.rollback()
        print(traceback.format_exc())

    else:
        connection.commit()
        print(f'Added local storage backend at {path[0]}')

    finally:
        connection.close()
        return

def list_storage_backends():
    # connect to database
    with pg.connect(host=crd.db.host, port=crd.db.port, database=crd.db.database, user=crd.db.user, password=crd.db.password) as connection:
        with connection.cursor() as cursor:
            cursor.execute('select * from prod.storage_backend')
            storage_backends = cursor.fetchall()
    fstring = '{:<5} {:<6} {:<62} {:<20} {}'
    print(fstring.format('ID', 'Type', 'Path', 'Creation Date', 'Notes'))
    for storage_backend in storage_backends:
        storage_id = storage_backend[0]
        url_prefix = storage_backend[1]
        storage_type = storage_backend[2]
        created_at = storage_backend[4].strftime('%Y-%m-%d %H:%M:%S')
        notes = storage_backend[6]
        print(fstring.format(storage_id, storage_type, url_prefix, created_at, notes))
    return storage_backends
