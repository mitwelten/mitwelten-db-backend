from datetime import datetime, timedelta
import os
import argparse
import signal
import logging
from functools import reduce

import psycopg2 as pg
from tqdm import tqdm

from config import crd
from batches import batches
from storage_backend import (
    get_storage_backend, create_local_storage_backend, list_storage_backends
)

iec_suffixes = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB']

def format_size(size, exponent=2):
    return str(round(size / pow(1024, exponent), 2)) + ' ' + iec_suffixes[exponent]

def main():
    argparser = argparse.ArgumentParser()

    subparsers = argparser.add_subparsers(dest='mode', help='Modes of operation')
    subparsers.required = True

    copy_parser = subparsers.add_parser('copy', help='Copy object from source to target storage')
    copy_parser.add_argument('-s', '--source', required=True, type=int, help='storage source')
    copy_parser.add_argument('-t', '--target', required=True, type=int, help='storage target')
    copy_parser.add_argument('--skip-existing', dest='skip_existing', action='store_true', help='skip (only) download if file exists in target storage')
    copy_parser.add_argument('batch_id', type=str, help='batch selection ID')

    info_parser = subparsers.add_parser('info', help='Info mode help')
    info_parser.add_argument('--backends', action='store_true', default=True, help='List storage backends')
    info_parser.add_argument('--batches', action='store_true', help='List batches')

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
        if args.batches:
            fstring = '{:<10} {:<8} {:<14} {}'
            print('Batches:')
            print(fstring.format('ID', 'Type', 'Target', 'Description'))
            for batch in batches:
                print(fstring.format(batch['id'], batch['type'], batch['target'], batch['description']))
            print()
        if args.backends:
            print('Storage backends:')
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

    batch = next((batch for batch in batches if batch['id'] == args.batch_id), None)
    if not batch:
        msg = f'Batch "{args.batch_id}" not found'
        logging.error(msg)
        print(f'{msg}, exiting...')
        return

    # List objects in batch
    with pg.connect(host=crd.db.host, port=crd.db.port, database=crd.db.database, user=crd.db.user, password=crd.db.password) as connection:
        with connection.cursor() as cursor:
            cursor.execute(batch['query'], (args.source, args.target))
            object_files = cursor.fetchall()

    total_filesize = reduce(lambda x, y: x + y, [f[2] for f in object_files])
    logging.info(f'batch: {args.batch_id}')
    msg = f'object files remaining in batch: {len(object_files)}, total filesize: {format_size(total_filesize, 3)}'
    logging.info(msg)
    print(msg)

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
    target_table = 'mm_files_image_storage' if batch['type'] == 'image' else 'mm_files_audio_storage'

    # Loop through object files
    with pg.connect(host=crd.db.host, port=crd.db.port, database=crd.db.database, user=crd.db.user, password=crd.db.password) as connection:

        update_ids = []
        def commit_changes():
            if update_ids:
                tqdm.write(f'Committing changes...')
                with connection.cursor() as cursor:
                    cursor.executemany(f'''
                        insert into {crd.db.schema}.{target_table} (file_id, storage_id) values (%s, %s)
                    ''', [(file_id, args.target) for file_id in update_ids])
                connection.commit()
                logging.info(f'Committed {len(update_ids)} changes')
                update_ids.clear()

        progress = tqdm(total=total_filesize, unit='B', unit_scale=True, unit_divisor=1024)
        for object_file in object_files:
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
                    update_ids.append(object_file[0])
                    if len(update_ids) == 1000 or timer + timedelta(seconds=900) < datetime.now():
                        commit_changes()
                        timer = datetime.now()
                finally:
                    progress.update(object_file[2])

        commit_changes()

if __name__ == '__main__':
    main()
