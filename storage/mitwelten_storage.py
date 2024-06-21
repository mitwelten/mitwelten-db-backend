'''
## Model process

- identify file to process
- create scaled version in memory (in the iteration)
- copy original file to archive
- update metadata in postgres
- write scaled version to active (or delete active original)

### next iteration

- implement service running closer to s3 storage (in REST API)
  - endpoint to request original file
  - option to request storage of scaled version upon original delivery
- GET /original/{file_id}
- once file is downloaded and written to archive, update metadata in postgres
- POST /archive/{file_id} (this sets the file to archived, without deleting anything)
- if scaled version is requested, write to active
- POST /scaled/{file_id}
  - scale image, replace original on active
  - update metadata in postgres
- or DELETE /original/{file_id} (should check that file exists in archive)

## Environment

S3 Storage
Local USB drive
'''

# standard library
from datetime import datetime, timedelta
import os
import sys
import argparse
import signal
from urllib.parse import urlparse
import logging

# external
from minio import Minio
from minio.datatypes import Object
from minio.error import S3Error
import psycopg2 as pg
from tqdm import tqdm

# local
from config import crd, LocalStorageDefaults
from batches import batches

def parse_kv_file(file_path):
    kv_dict = {}
    with open(file_path, 'r') as f:
        for line in f:
            key, value = line.strip().split('=', 1)
            kv_dict[key] = value
    return kv_dict

def process_file(object_name, source_id, target_id):
    # connect to database
    with pg.connect(host=crd.db.host, port=crd.db.port, database=crd.db.database, user=crd.db.user, password=crd.db.password) as connection:
        with connection.cursor() as cursor:
            cursor.execute('select * from prod.storage_backend where storage_id = %s', (source_id,))
            source = cursor.fetchone()
            cursor.execute('select * from prod.storage_backend where storage_id = %s', (target_id,))
            target = cursor.fetchone()
            cursor.execute('select * from prod.files_image where object_name = %s', (object_name,))
            object_file = cursor.fetchone()

            cursor.execute('''
                select * from prod.mm_files_image_storage mm
                left join prod.storage_backend sb on mm.storage_id = sb.storage_id
                where mm.file_id = %s
            ''', (object_file[0],))
            storage_versions = cursor.fetchall()

    # check if object exists in source
    source_record = None
    try:
        for version in storage_versions:
            if version[1] == source_id:
                source_record = version
                break
        if not source_record:
            raise Exception('No record found in source storage.')
    except:
        print(f'Object {object_name} not found in source storage {source_id}.')
        return

    # check if object exists in target
    try:
        for version in storage_versions:
            if version[1] == target_id:
                raise Exception('Object already has record in target storage.')
    except Exception as e:
        print(object_name, e)
        return

    # test if the source is accessible
    if str(source[2]).lower() == 's3':
        url_prefix = source[1]
        parsed_url = urlparse(url_prefix)
        source_minio_host = parsed_url.netloc
        source_minio_bucket = parsed_url.path.strip('/')

        source_storage = Minio(
            source_minio_host,
            access_key=crd.minio.access_key,
            secret_key=crd.minio.secret_key,
        )
        if not source_storage.bucket_exists(source_minio_bucket):
            print(f'Bucket {source_minio_bucket} does not exist.')
            return
        else: print(f'Bucket {source_minio_bucket} exists.')

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

def main():
    argparser = argparse.ArgumentParser()

    subparsers = argparser.add_subparsers(dest='mode', help='Modes of operation')
    subparsers.required = True  # Python 3.7 and above requires setting this explicitly

    copy_parser = subparsers.add_parser('copy', help='Copy object from source to target storage')
    copy_parser.add_argument('-o', '--object', required=False, type=str, help='object name')
    copy_parser.add_argument('-s', '--source', required=True, type=int, help='storage source')
    copy_parser.add_argument('-t', '--target', required=True, type=int, help='storage target')
    copy_parser.add_argument('--skip-existing', dest='skip_existing', action='store_true', help='skip (only) download if file exists in target storage')
    copy_parser.add_argument('batch_id', type=int, help='batch selection ID')

    info_parser = subparsers.add_parser('info', help='Info mode help')
    info_parser.add_argument('-b', '--backends', action='store_true', help='List storage backends')

    args = argparser.parse_args()

    fileprefix=f'{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}'
    logging.basicConfig(level=logging.INFO, filename=f'{fileprefix}_storage-layer.log', format='%(asctime)s %(levelname)s: %(message)s')

    if args.mode == 'info':
        if args.backends:
            list_storage_backends()
        return

    storage = Minio(
        crd.minio.host,
        access_key=crd.minio.access_key,
        secret_key=crd.minio.secret_key,
    )
    bucket_exists = storage.bucket_exists(crd.minio.bucket)
    if not bucket_exists:
        print(f'Bucket {crd.minio.bucket} does not exist.')
        return

    logging.info(f'mode: {args.mode}')
    logging.info(f'source: {args.source} ({str(source[2]).lower()}, {source[1]})')
    logging.info(f'target: {args.target} ({str(target[2]).lower()}, {target[1]})')
    logging.info(f'batch: {args.batch_id}')

    batch_query = batches[args.batch_id]

    # connect to database
    with pg.connect(host=crd.db.host, port=crd.db.port, database=crd.db.database, user=crd.db.user, password=crd.db.password) as connection:
        with connection.cursor() as cursor:
            cursor.execute('select * from prod.storage_backend where storage_id = %s', (args.source,))
            source = cursor.fetchone()
            cursor.execute('select * from prod.storage_backend where storage_id = %s', (args.target,))
            target = cursor.fetchone()
            cursor.execute(batch_query, (args.source, args.target))
            object_files = cursor.fetchall()

    logging.info(f'object files remaining in batch: {len(object_files)}')
    # test if the source is accessible
    if str(source[2]).lower() == 's3':
        url_prefix = source[1]
        parsed_url = urlparse(url_prefix)
        source_minio_host = parsed_url.netloc
        source_minio_bucket = parsed_url.path.strip('/')

        source_storage = Minio(
            source_minio_host,
            access_key=crd.minio.access_key,
            secret_key=crd.minio.secret_key,
        )
        if not source_storage.bucket_exists(source_minio_bucket):
            print(f'Bucket {source_minio_bucket} does not exist.')
            return
        else: print(f'Bucket {source_minio_bucket} exists.')

    # -------------------------
    if str(target[2]).lower() == 'local':
        url_prefix = target[1]
        # test if the target is accessible
        while True:
            if not os.path.exists(url_prefix):
                print(f"URL prefix {url_prefix} does not exist.")
                # ask the user to input the path to the storage device or directory
                url_prefix = input("Enter the path to the storage device or directory: ")
                if len(url_prefix) == 0:
                    print('exiting')
                    return
            else: break

        # test if the target is writable
        if not os.access(url_prefix, os.W_OK):
            print(f"URL prefix {url_prefix} is not writable.")
            return

        # read the dot-file to identify the storage device
        lsd = LocalStorageDefaults()
        target_properties = parse_kv_file(os.path.join(url_prefix, lsd.dot_file_name))

        # test if target_properties match the target storage record
        if target_properties['storage_id'] != str(target[0]):
            print(f"Storage ID in dot-file does not match target storage record.")
            return
        if target_properties['device_label'] != str(target[-1]):
            print(f"Device label in dot-file does not match notes in target storage record.")
            return
        if target_properties['created_at'] != str(target[4]):
            print(f"Creation date in dot-file does not match creation date in target storage record.")
            return

        abs_storage_dir = os.path.join(url_prefix, target_properties['storage_dir'])
        if not os.access(abs_storage_dir, os.W_OK):
            print(f"Target {abs_storage_dir} is not writable.")
            return

    keep_running = True

    def signal_handler(signal, frame):
        nonlocal keep_running
        keep_running = False

    # Register the signal handler
    signal.signal(signal.SIGINT, signal_handler)  # Handle Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Handle SIGTERM

    timer = datetime.now()

    # Loop through object files
    with pg.connect(host=crd.db.host, port=crd.db.port, database=crd.db.database, user=crd.db.user, password=crd.db.password) as connection:
        for object_file in tqdm(object_files):
            if not keep_running:
                tqdm.write('Interrupt received. Exiting...')
                break
            object_name = object_file[1]

            if str(target[2]).lower() == 's3':
                ...

            if str(target[2]).lower() == 'local':

                try:
                    # Copy object to target storage
                    abs_object_name = os.path.join(abs_storage_dir, *object_name.split('/'))
                    tqdm.write(abs_object_name)
                    os.makedirs(os.path.dirname(abs_object_name), exist_ok=True)
                    if args.skip_existing and os.path.exists(abs_object_name):
                        tqdm.write(f'File {abs_object_name} already exists.')
                    else:
                        response = source_storage.get_object(source_minio_bucket, object_name)
                        with open(abs_object_name, 'wb') as f:
                            f.write(response.read())
                except Exception as e:
                    logging.error(f'Error copying object {object_name} to target storage: {e}')
                else:
                    # If the object is successfully written to the target storage, update the database
                    with connection.cursor() as cursor:
                        cursor.execute('''
                            insert into prod.mm_files_image_storage (file_id, storage_id) values (%s, %s)
                        ''', (object_file[0], args.target))
                # commit every 15 minutes
                if timer + timedelta(seconds=900) < datetime.now():
                    logging.info('Committing changes...')
                    timer = datetime.now()
                    connection.commit()

    return

    # get object
    response = storage.get_object(crd.minio.bucket, object_name)
    print(response.headers)
    with open('test.jpg', 'wb') as f:
        f.write(response.read())

    # # put object
    # object_name = 'walk/public/2021/09/2021-09-01_13-00-00_UTC.jpg'
    # with open('test.jpg', 'rb') as f:
    #     response = storage.put_object(crd.minio.bucket, object_name, f, length=-1)
    # print(response.headers)

if __name__ == '__main__':
    main()
