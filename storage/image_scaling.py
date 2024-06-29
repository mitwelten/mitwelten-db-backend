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

import psycopg2 as pg
from PIL import Image
from tqdm import tqdm
from tqdm.contrib.concurrent import thread_map

from config import crd
from type_definitions import image_types
from storage_backend import S3Storage, get_storage_backend

def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument('--target_type', type=int, default=1)
    args = argparser.parse_args()
    target_type = [t for t in image_types if t.identifier == args.target_type][0]
    if not target_type:
        print('Invalid target type.')
        return
    print(f'Target format: {target_type.format_name}, target size: {target_type.dimensions}')

    storage_backend = get_storage_backend(crd.storage_backend)
    if storage_backend.type != 's3':
        print('Processing images only supported for S3 storage backends, in place.')
        return
    s3 = storage_backend.storage

    with pg.connect(host=crd.db.host, port=crd.db.port, database=crd.db.database, user=crd.db.user, password=crd.db.password) as connection:
        with connection.cursor() as cursor:
            # TODO: make sure an original version of each image exists
            query = '''
            select f.file_id, object_name, sb.storage_id
            from prod.mm_files_image_storage mfs
            left join prod.files_image f on f.file_id = mfs.file_id
            left join prod.storage_backend sb on mfs.storage_id = sb.storage_id
            where sb.priority = 0 -- assuming priority 2 is complete for 820
            and mfs.type = 0 -- 0=original, 1=compressed
            and f.deployment_id = 820
            order by f.time;
            '''
            cursor.execute(query)
            records = cursor.fetchall()
    if not records:
        print('No records found.')
        return

    def process_record(record):
        file_id, object_name, source_storage_id = record
        try:
            response = s3.get_object(storage_backend.bucket, object_name)

            image = Image.open(response)
            image.thumbnail(target_type.dimensions, Image.Resampling.LANCZOS)

            object_name_parts = os.path.splitext(object_name)
            target_object_name = object_name_parts[0] + '.' + target_type.extension

            file = BytesIO()
            file.name = target_object_name
            image.save(file, target_type.format_name)
            file.seek(0)

            s3.put_object(storage_backend.bucket, target_object_name, file, file.getbuffer().nbytes)
            s3.set_object_tags(crd.minio.bucket, target_object_name, s3.get_object_tags(crd.minio.bucket, object_name))

        except Exception as e:
            tqdm.write(traceback.format_exc())

        else:
            return file_id, object_name, source_storage_id, target_object_name

    def remove_original_objects(record):
        file_id, object_name, source_storage_id, target_object_name = record
        s3.remove_object(storage_backend.bucket, object_name)

    num_threads = 8
    processed_records = thread_map(process_record, records, max_workers=num_threads)
    processed_records = [record for record in processed_records if record]
    print('Processed records:', len(processed_records))

    try:
        print('Updating records...')
        with pg.connect(host=crd.db.host, port=crd.db.port, database=crd.db.database, user=crd.db.user, password=crd.db.password) as connection:
            with connection.cursor() as cursor:
                # set mm_files_image_storage.type = 1 # 0=original, 1=compressed
                for record in processed_records:
                    file_id, object_name, source_storage_id, target_object_name = record
                    cursor.execute('''
                    update prod.mm_files_image_storage set type = 1, updated_at = current_timestamp
                    where storage_id = %s and file_id = %s;
                    ''', (source_storage_id, file_id))
    except Exception as e:
        print(traceback.format_exc())
    else:
        print('Removing original objects...')
        thread_map(remove_original_objects, processed_records, max_workers=num_threads)

if __name__ == '__main__':
    main()
