import argparse
import traceback
from datetime import datetime

from minio import Minio
import psycopg2 as pg
from jinja2 import Environment, FileSystemLoader

from config import crd, LocalStorageDefaults
import os

'''
Add records to the storage_backend table to create a new storage backend.

If the storage backend to be added is a physical device, add a dot-file to identify it, i.e. .mitwelten-storage-id
To add a physical device , use the option --type=local and the path to the directory containing the dot-file.

This CLI will create:

1. a record in the storage_backend table with the url_prefix set to the path to the directory
2. a dot-file in the directory to identify it as a storage backend
3. README.md file in the directory with instructions on how to use the storage backend
4. a subdirectory "archive" in the directory to store archived files
'''

def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument('-t', '--type', required=True, help='storage type')
    argparser.add_argument('-p', '--priority', required=True, help='storage priority')
    argparser.add_argument('-n', '--notes', required=True, help='storage description (i.e. HDD label)')
    argparser.add_argument('path', type=str, help='storage path', nargs=1)
    args = argparser.parse_args()

    if args.type == 'local':
        lsd = LocalStorageDefaults()
        lsd.priority = args.priority
        lsd.device_label = args.notes.strip().replace('\n', ',')[:128]

        # Check if the directories and files already exist
        try:
            if os.path.exists(args.path[0]):
                print(f'[OK] Directory {args.path[0]} exists.')
                lsd.original_path = args.path[0]
            else:
                raise Exception(f'Directory {args.path[0]} does not exist.')

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
                ''', (lsd.original_path, args.type, lsd.priority, lsd.device_label))
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
            archive_dir = os.path.join(args.path[0], 'archive')
            os.makedirs(archive_dir)

        except Exception as e:
            connection.rollback()
            print(traceback.format_exc())

        else:
            connection.commit()
            print(f'Added local storage backend at {args.path[0]}')

        finally:
            connection.close()
            return

    return

    # example for minio storage
    # python create_storage_backend.py --type=minio http://minio3.campusderkuenste.ch/ixdm-mitwelten/
    storage = Minio(
        crd.minio.host,
        access_key=crd.minio.access_key,
        secret_key=crd.minio.secret_key,
    )
    bucket_exists = storage.bucket_exists(crd.minio.bucket)
    if not bucket_exists:
        print(f'Bucket {crd.minio.bucket} does not exist.')
        return

if __name__ == '__main__':
    main()
