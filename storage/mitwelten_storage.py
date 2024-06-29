from datetime import datetime, timedelta
import os
import argparse
import signal
import logging

import psycopg2 as pg
from tqdm import tqdm

from config import crd
from batches import batches
from storage_backend import (
    get_storage_backend, create_local_storage_backend, list_storage_backends
)

def main():
    argparser = argparse.ArgumentParser()

    subparsers = argparser.add_subparsers(dest='mode', help='Modes of operation')
    subparsers.required = True

    copy_parser = subparsers.add_parser('copy', help='Copy object from source to target storage')
    copy_parser.add_argument('-s', '--source', required=True, type=int, help='storage source')
    copy_parser.add_argument('-t', '--target', required=True, type=int, help='storage target')
    copy_parser.add_argument('--skip-existing', dest='skip_existing', action='store_true', help='skip (only) download if file exists in target storage')
    copy_parser.add_argument('batch_id', type=int, help='batch selection ID')

    info_parser = subparsers.add_parser('info', help='Info mode help')
    info_parser.add_argument('-b', '--backends', action='store_true', default=True, help='List storage backends')

    create_parser = subparsers.add_parser('create', help='Create storage backend')
    create_parser.add_argument('-t', '--type', required=True, help='storage type')
    create_parser.add_argument('-p', '--priority', required=True, help='storage priority')
    create_parser.add_argument('-n', '--notes', required=True, help='storage description (i.e. HDD label)')
    create_parser.add_argument('path', type=str, help='storage path', nargs=1)

    args = argparser.parse_args()

    # -------------------------------------------------------------------------
    # List storage backends
    # -------------------------------------------------------------------------
    if args.mode == 'info':
        if args.backends:
            list_storage_backends()
        return

    # -------------------------------------------------------------------------
    # Create storage backend
    # -------------------------------------------------------------------------
    if args.mode == 'create':
        if args.type == 'local':
            create_local_storage_backend(args.path, args.priority, args.notes)
        return

    # -------------------------------------------------------------------------
    # Copy objects from source to target storage
    # -------------------------------------------------------------------------
    fileprefix=f'logs/{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}'
    if not os.path.exists('logs'):
        os.makedirs('logs')
    logging.basicConfig(level=logging.INFO, filename=f'{fileprefix}_storage-layer.log', format='%(asctime)s %(levelname)s: %(message)s')
    logging.info(f'mode: {args.mode}')

    batch_query = batches[args.batch_id]

    # List objects in batch
    with pg.connect(host=crd.db.host, port=crd.db.port, database=crd.db.database, user=crd.db.user, password=crd.db.password) as connection:
        with connection.cursor() as cursor:
            cursor.execute(batch_query, (args.source, args.target))
            object_files = cursor.fetchall()

    logging.info(f'batch: {args.batch_id}')
    logging.info(f'object files remaining in batch: {len(object_files)}')

    try:
        source_storage_backend = get_storage_backend(args.source)
        target_storage_backend = get_storage_backend(args.target)

        if source_storage_backend.type == 's3':
            source_storage = source_storage_backend.storage
            logging.info(f'source: {args.source} ({source_storage_backend})')
        else:
            logging.error(f'Unsupported source storage type: {source_storage_backend.type}')
            return

        if target_storage_backend.type == 'local':
            target_storage = target_storage_backend.path
            logging.info(f'target: {args.target} ({target_storage_backend})')
        else:
            logging.error(f'Unsupported target storage type: {target_storage_backend.type}')
            return

    except Exception as e:
        logging.error(f'Error setting up storage backends: {e}')
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

            if target_storage_backend.type == 's3':
                ...

            if target_storage_backend.type == 'local':

                try:
                    # Copy object to target storage
                    abs_object_name = os.path.join(target_storage, *object_name.split('/'))
                    tqdm.write(abs_object_name)
                    os.makedirs(os.path.dirname(abs_object_name), exist_ok=True)
                    if args.skip_existing and os.path.exists(abs_object_name):
                        # tqdm.write(f'File {abs_object_name} already exists.')
                        ...
                    else:
                        response = source_storage.get_object(source_storage_backend.bucket, object_name)
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
                # Commit every 15 minutes
                if timer + timedelta(seconds=900) < datetime.now():
                    logging.info('Committing changes...')
                    timer = datetime.now()
                    connection.commit()

if __name__ == '__main__':
    main()
