'''
- query image records
- loop through records
    - download image from s3 into memory
    - scale image
    - upload scaled data as image to s3
    - update mm_files_image_storage.type to 1
    - remove original image from s3
'''

import os
import traceback
from io import BytesIO
import argparse
from typing import List, Tuple
from datetime import datetime

import psycopg2 as pg
from PIL import Image
from tqdm import tqdm
from tqdm.contrib.concurrent import thread_map

from config import crd
from type_definitions import image_types
from storage_backend import S3Storage, get_storage_backend

NUM_THREADS = 10

def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument('-s', '--source', required=False, type=int, help='storage source')
    argparser.add_argument('-t', '--target', required=True, type=int, help='storage target')
    argparser.add_argument('--remove', action='store_true', help='remove original images after processing')
    argparser.add_argument('--target_type', type=int, default=1)
    argparser.add_argument('deployment_id', type=int, help='deployment selection (ID)')
    args = argparser.parse_args()

    fileprefix=f'{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}'

    target_type = [t for t in image_types if t.identifier == args.target_type][0]
    if not target_type or target_type.format_name != 'WEBP':
        print('Invalid target type.')
        return
    print(f'Target format: {target_type.format_name}, target size: {target_type.dimensions}')

    in_place = True
    if not args.source or args.source == args.target:
        print(f'In-place processing on backend {args.target}.')
        args.source = args.target
    else:
        print(f'Processing from backend {args.source} to backend {args.target}.')
        storage_backend_source = get_storage_backend(args.source)
        print('source:', storage_backend_source)
        if storage_backend_source.type != 's3':
            print('Processing images only supported for S3 storage backends')
            return
        in_place = False

    storage_backend = get_storage_backend(args.target)
    print('inplace/target:', storage_backend)
    if storage_backend.type != 's3':
        print('Processing images only supported for S3 storage backends')
        return

    with pg.connect(host=crd.db.host, port=crd.db.port, database=crd.db.database, user=crd.db.user, password=crd.db.password) as connection:
        with connection.cursor() as cursor:
            cursor.execute('''
            select node_label, d.description
            from prod.deployments d
            left join prod.nodes n on d.node_id = n.node_id
            where deployment_id = %s;
            ''', (args.deployment_id,))
            deployment = cursor.fetchone()
            if not deployment:
                print('Deployment not found.')
                return

            # TODO: make sure an original version of each image exists
            query = '''
            select f.file_id, object_name --, sb.storage_id
            from prod.mm_files_image_storage mfs
            left join prod.files_image f on f.file_id = mfs.file_id
            left join prod.storage_backend sb on mfs.storage_id = sb.storage_id
            where sb.priority = 0 -- assuming priority 2 is complete for 820
            and sb.storage_id = %s
            and mfs.type = 0 -- 0=original, 1=compressed
            and f.deployment_id = %s
            order by f.deployment_id, f.time;
            '''
            cursor.execute(query, (args.source, args.deployment_id))
            records: List[Tuple[int, str]] = cursor.fetchall() # file_id, object_name
    if not records:
        print('No records found.')
        return

    print(f'{len(records)} found for deployment {args.deployment_id} ({deployment[0]}, {deployment[1]})')
    print('deleting original objects after processing' if args.remove else 'object will not be deleted from source')
    processed_records = []

    if in_place:
        print('in-place processing on backend', args.target)
        if input('proceed? [Y|n]: ').lower() == 'n':
            return
        processed_records = in_place_processing(records, target_type, storage_backend)
    else:
        print(f'processing from source {args.source} to target {args.target}')
        if input('proceed? [Y|n]: ').lower() == 'n':
            return
        processed_records = source_target_processing(records, target_type, storage_backend_source, storage_backend, args.remove)

    if not processed_records:
        return
    print('processed records:', len(processed_records))

    if args.remove and processed_records:
        # only produce a file to be used with mc rm --versions --force
        print('creating input file for mc remove command...')
        removed_file = f'{fileprefix}_deployment_{args.deployment_id}_to_remove.txt'
        backend = storage_backend if in_place else storage_backend_source
        with open(removed_file, 'w') as f:
            f.write('\n'.join([f'{backend.alias}/{backend.bucket}/{object_name}' for f_id, object_name, t in processed_records]))
        print('first line:', f'{backend.alias}/{backend.bucket}/{processed_records[0][1]}')
        print('next: parallel -j10 mc rm --versions --force {} <', removed_file)

        # def remove_original_objects(record):
        #     file_id, object_name, target_object_name = record
        #     try:
        #         s3.remove_object(storage_backend.bucket, object_name)
        #     except:
        #         tqdm.write(traceback.format_exc())
        #         return None
        #     else:
        #         return object_name
        # removed = thread_map(remove_original_objects, processed_records, max_workers=NUM_THREADS)
        # removed = [r for r in removed if r]
        # # write removed objects to file for removal of delete markers
        # removed_file = f'{fileprefix}_{args.deployment_id}_removed.txt'
        # with open(removed_file, 'w') as f:
        #     f.write('\n'.join(removed))
        # if len(removed) != len(processed_records):
        #     print(f'Failed to remove {len(processed_records) - len(removed)} objects.')
        # print('next: parallel -j10 mc rm --versions --force server_id/bucket/{} <', removed_file)
    else:
        print('not removing original objects')

def in_place_processing(records: List[Tuple[int, str]], target_type, storage_backend: S3Storage):
    s3 = storage_backend.storage

    def process_record(record: Tuple[int, str]):
        file_id, object_name = record
        # file_id, object_name, source_storage_id = record # when in place, the query should not filter by source storage, but any storage matching priority = 0
        try:
            response = s3.get_object(storage_backend.bucket, object_name)

            image = Image.open(response)
            if image.size[0] > target_type.dimensions[0] or image.size[1] > target_type.dimensions[1]:
                image.thumbnail(target_type.dimensions, Image.Resampling.LANCZOS)

            object_name_parts = os.path.splitext(object_name)
            target_object_name = object_name_parts[0] + '.' + target_type.extension

            file = BytesIO()
            file.name = target_object_name
            image.save(file, target_type.format_name)
            file.seek(0)

            s3.put_object(storage_backend.bucket, target_object_name, file, file.getbuffer().nbytes)
            tags = s3.get_object_tags(crd.minio.bucket, object_name)
            if tags:
                s3.set_object_tags(crd.minio.bucket, target_object_name, s3.get_object_tags(crd.minio.bucket, object_name))

        except Exception as e:
            tqdm.write(traceback.format_exc())

        else:
            return file_id, object_name, target_object_name

    processed_records = thread_map(process_record, records, max_workers=NUM_THREADS)
    processed_records = [record for record in processed_records if record]
    if not processed_records:
        return

    try:
        print('updating records...')
        with pg.connect(host=crd.db.host, port=crd.db.port, database=crd.db.database, user=crd.db.user, password=crd.db.password) as connection:
            with connection.cursor() as cursor:
                # set mm_files_image_storage.type = 1 # 0=original, 1=compressed
                for record in processed_records:
                    file_id, object_name, target_object_name = record
                    cursor.execute('''
                    update prod.mm_files_image_storage set type = 1, updated_at = current_timestamp
                    where storage_id = %s and file_id = %s;
                    ''', (storage_backend.storage_id, file_id))
    except Exception as e:
        print(traceback.format_exc())
    else:
        return processed_records

def source_target_processing(records: List[Tuple[int, str]], target_type, source_backend: S3Storage, target_backend: S3Storage, remove=False):
    s3_source = source_backend.storage
    s3_target = target_backend.storage

    def process_record(record: Tuple[int, str]):
        file_id, object_name = record
        try:
            response = s3_source.get_object(source_backend.bucket, object_name)

            image = Image.open(response)
            if image.size[0] > target_type.dimensions[0] or image.size[1] > target_type.dimensions[1]:
                image.thumbnail(target_type.dimensions, Image.Resampling.LANCZOS)

            object_name_parts = os.path.splitext(object_name)
            target_object_name = object_name_parts[0] + '.' + target_type.extension

            file = BytesIO()
            file.name = target_object_name
            image.save(file, target_type.format_name)
            file.seek(0)

            s3_target.put_object(target_backend.bucket, target_object_name, file, file.getbuffer().nbytes)
            tags = s3_source.get_object_tags(source_backend.bucket, object_name)
            if tags:
                s3_target.set_object_tags(target_backend.bucket, target_object_name, tags)

        except Exception as e:
            tqdm.write(traceback.format_exc())
            return

        else:
            return file_id, object_name, target_object_name

    processed_records = thread_map(process_record, records, max_workers=NUM_THREADS)
    processed_records = [record for record in processed_records if record]
    if not processed_records:
        return

    try:
        print('updating records...')
        with pg.connect(host=crd.db.host, port=crd.db.port, database=crd.db.database, user=crd.db.user, password=crd.db.password) as connection:
            with connection.cursor() as cursor:
                # set mm_files_image_storage.type = 1 # 0=original, 1=compressed
                if remove:
                    # if original images are to be deleted, update records in place
                    cursor.executemany(f'''
                    update {crd.db.schema}.mm_files_image_storage set type = 1, storage_id = %s, updated_at = current_timestamp
                    where storage_id = %s and file_id = %s and type = 0;
                    ''', [(target_backend.storage_id, source_backend.storage_id, f_id) for f_id, o, t in processed_records])
                else:
                    cursor.executemany(f'''
                    insert into {crd.db.schema}.mm_files_image_storage(file_id, storage_id, type)
                    values (%s, %s, 1);
                    ''', [(f_id, target_backend.storage_id) for f_id, o, t in processed_records])
    except Exception as e:
        print(traceback.format_exc())
    else:
        return processed_records

if __name__ == '__main__':
    main()
