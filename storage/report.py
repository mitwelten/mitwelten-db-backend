import os
import argparse
import sqlite3
from datetime import datetime
from typing import List

from jinja2 import Environment, FileSystemLoader
import psycopg2 as pg
from psycopg2.extras import DictCursor, DictRow

from config import crd
from mitwelten_storage import format_size
from storage_backend import (
    NoLocalStoragePathError, StorageBackendNotFoundError, get_storage_backend
)

def main():
    argparser = argparse.ArgumentParser(description='generate reports on mitwelten storage backends')

    subparsers = argparser.add_subparsers(dest='mode', help='modes of operation')
    subparsers.required = True

    archive_parser = subparsers.add_parser('archive', help='reports on archived data', description='reports on archived data')
    archive_parser.add_argument('-c', '--csv', dest='csv', action='store_true', help='csv output (not implemented)')
    archive_parser.add_argument('backend_id', type=str, help='storage backend ID')

    compression_parser = subparsers.add_parser('compression', help='reports on compressed data (not implemented)', description='reports on compressed data (not implemented)')

    args = argparser.parse_args()

    if args.mode == 'archive':
        # check if local storage is connected
        try:
            print('checking if storage backend is accessible...')
            storage_backend = get_storage_backend(args.backend_id)
        except (StorageBackendNotFoundError, NoLocalStoragePathError) as e:
            storage_backend = None
            print(f'proceeding to generate report in cwd for storage backend {args.backend_id}...')
        except ValueError as e:
            print(e)
            return
        else:
            print(f'storage backend: {storage_backend}')

        if not storage_backend or storage_backend.type != 'local':
            archive_base_path = os.getcwd()
            readme_file_path = os.path.join(archive_base_path, f'REPORT_backend_{args.backend_id}.md')
            db_path = os.path.join(archive_base_path, f'archive_index_backend_{args.backend_id}.db')
        else:
            archive_base_path = os.path.dirname(storage_backend.path)
            readme_file_path = os.path.join(archive_base_path, 'REPORT.md')
            db_path = os.path.join(archive_base_path, 'archive_index.db')

        print(f'archive base path: {archive_base_path}')

        with pg.connect(host=crd.db.host, port=crd.db.port, database=crd.db.database, user=crd.db.user, password=crd.db.password, cursor_factory=DictCursor) as connection:
            with connection.cursor() as cursor:
                print('querying image records...')
                image_records_query = '''
                select f.* from prod.mm_files_image_storage m
                left join prod.files_image f on m.file_id = f.file_id
                where m.storage_id = %s and m.type = 0
                -- limit 10;
                '''
                cursor.execute(image_records_query, (args.backend_id,))
                image_records = cursor.fetchall()

                print('querying audio records...')
                audio_records_query = '''
                select f.* from prod.mm_files_audio_storage m
                left join prod.files_audio f on m.file_id = f.file_id
                where m.storage_id = %s and m.type = 0
                -- limit 10;
                '''
                cursor.execute(audio_records_query, (args.backend_id,))
                audio_records = cursor.fetchall()

                print('querying deployments...')
                deployment_ids = tuple(set([r['deployment_id'] for r in image_records]).union(set([r['deployment_id'] for r in audio_records])))
                deployments_query = '''
                select d.deployment_id, d."location", d."period", d.description,
                n.node_id, node_label, n."type", serial_number, platform, connectivity, power, hardware_version, software_version, n.description as node_description, created_at, updated_at
                from prod.deployments d
                left join prod.nodes n on n.node_id = d.node_id
                where d.deployment_id in %s
                '''
                cursor.execute(deployments_query, (deployment_ids,))
                deployments: List[DictRow] = cursor.fetchall()

        # create database
        print(f'creating index database at {db_path}...')
        database = sqlite3.connect(db_path)
        c = database.cursor()
        c.execute('''create table if not exists image_records (
            file_id integer primary key,
            object_name text,
            sha256 text unique,
            timestamp integer,
            deployment_id integer,
            file_size integer,
            resolution_x integer,
            resolution_y integer,
            created_at integer,
            updated_at integer,
            foreign key (deployment_id) references deployments(deployment_id)
        )''')
        c.execute('''create table if not exists audio_records (
            file_id integer primary key,
            object_name text,
            sha256 text unique,
            timestamp integer,
            deployment_id integer,
            file_size integer,
            format text,
            bit_depth integer,
            channels integer,
            duration real,
            sample_rate integer,
            serial_number text,
            source text,
            gain text,
            filter text,
            battery text,
            temperature text,
            rec_end_status text,
            created_at integer,
            updated_at integer,
            foreign key (deployment_id) references deployments(deployment_id)
        )''')
        c.execute('''create table if not exists deployments (
            deployment_id integer primary key,
            location_lon real,
            location_lat real,
            period_start integer,
            period_end integer,
            description text,
            node_id integer,
            node_label text,
            type text,
            serial_number text,
            platform text,
            connectivity text,
            power text,
            hardware_version text,
            software_version text,
            node_description text,
            created_at integer,
            updated_at integer
        )''')
        c.execute('create index if not exists files_object_name_idx on image_records (object_name)')
        c.execute('create index if not exists files_sha256_idx on image_records (sha256)')
        database.commit()

        print('inserting deployments...')
        deployment_field_map = {
            'deployment_id': 'deployment_id',
            'location_lon': lambda x: float(x['location'].split(',')[0].strip('()')),
            'location_lat': lambda x: float(x['location'].split(',')[1].strip('()')),
            'period_start': lambda x: int(x['period'].lower.timestamp()),
            'period_end': lambda x: int(x['period'].lower.timestamp()),
            'description': 'description',
            'node_id': 'node_id',
            'node_label': 'node_label',
            'type': 'type',
            'serial_number': 'serial_number',
            'platform': 'platform',
            'connectivity': 'connectivity',
            'power': 'power',
            'hardware_version': 'hardware_version',
            'software_version': 'software_version',
            'node_description': 'node_description',
            'created_at': lambda x: int(x['created_at'].timestamp()),
            'updated_at': lambda x: int(x['updated_at'].timestamp())
        }
        deployment_prep = []
        for deployment in deployments:
            deployment_prep.append({k: deployment[v] if not callable(v) else v(deployment) for k, v in deployment_field_map.items()})
        c.executemany('''insert or ignore into deployments values (
            :deployment_id, :location_lon, :location_lat, :period_start, :period_end, :description, :node_id, :node_label, :type, :serial_number, :platform, :connectivity, :power, :hardware_version, :software_version, :node_description, :created_at, :updated_at
        )''', deployment_prep)
        database.commit()

        print('inserting image records...')
        image_field_map = {
            'file_id': 'file_id',
            'object_name': 'object_name',
            'sha256': 'sha256',
            'timestamp': lambda x: int(x['time'].timestamp()),
            'deployment_id': 'deployment_id',
            'file_size': 'file_size',
            'resolution_x': lambda x: x['resolution'][0],
            'resolution_y': lambda x: x['resolution'][1],
            'created_at': lambda x: int(x['created_at'].timestamp()),
            'updated_at': lambda x: int(x['updated_at'].timestamp())
        }
        image_records_prep = []
        for record in image_records:
            record_prep = {k: record[v] if not callable(v) else v(record) for k, v in image_field_map.items()}
            image_records_prep.append(record_prep)
        c.executemany('''insert or ignore into image_records values (
            :file_id, :object_name, :sha256, :timestamp, :deployment_id, :file_size, :resolution_x, :resolution_y, :created_at, :updated_at
        )''', image_records_prep)
        database.commit()

        print('inserting audio records...')
        audio_field_map = {
            'file_id': 'file_id',
            'object_name': 'object_name',
            'sha256': 'sha256',
            'timestamp': lambda x: int(x['time'].timestamp()),
            'deployment_id': 'deployment_id',
            'file_size': 'file_size',
            'format': 'format',
            'bit_depth': 'bit_depth',
            'channels': 'channels',
            'duration': 'duration',
            'sample_rate': 'sample_rate',
            'serial_number': 'serial_number',
            'source': 'source',
            'gain': 'gain',
            'filter': 'filter',
            'battery': 'battery',
            'temperature': 'temperature',
            'rec_end_status': 'rec_end_status',
            'created_at': lambda x: int(x['created_at'].timestamp()),
            'updated_at': lambda x: int(x['updated_at'].timestamp())
        }
        audio_records_prep = []
        for record in audio_records:
            record_prep = {k: record[v] if not callable(v) else v(record) for k, v in audio_field_map.items()}
            audio_records_prep.append(record_prep)
        c.executemany('''insert or ignore into audio_records values (
            :file_id, :object_name, :sha256, :timestamp, :deployment_id, :file_size, :format, :bit_depth, :channels, :duration, :sample_rate, :serial_number, :source, :gain, :filter, :battery, :temperature, :rec_end_status, :created_at, :updated_at
        )''', audio_records_prep)
        database.commit()

        # create report from data stored in db_path
        print('generating report...')
        database.row_factory = sqlite3.Row
        c = database.cursor()
        c.execute('''
        with records_stats as (
            select file_type, deployment_id, count(*) as total_records, sum(file_size) as total_size from (
                select file_id, file_size, deployment_id, 'image' as file_type from image_records
                union all
                select file_id, file_size, deployment_id, 'audio' as file_type from audio_records
            ) as records
            group by file_type, deployment_id
        )
        select file_type, node_label, deployments.deployment_id, type, period_start, period_end, total_records, total_size, description from records_stats
        left join deployments on records_stats.deployment_id = deployments.deployment_id
        order by file_type, type, node_label, period_start;
        ''')
        deployment_stats = c.fetchall()

        # generate markdow table from deployment_stats
        report_content = []
        columns = ['node_label', 'deployment_id', 'type', 'period_start', 'period_end', 'total_records', 'total_size', 'description']
        headers = ['Label', 'D ID', 'Type', 'Date Start', 'Date End', 'N', 'GiB', 'Description']

        col_widths = [max(len(str(row[col])) for row in deployment_stats) for col in columns]
        fstring = '| ' + ' | '.join([f'{{:<{w}}}' for w in col_widths]) + ' |'
        report_content.append(fstring.format(*headers))
        report_content.append(fstring.format(*['-' * w for w in col_widths]))

        for row in deployment_stats:
            try:
                row = {k: v for k, v in dict(row).items() if k in columns}
                row['period_start'] = datetime.fromtimestamp(row['period_start']).strftime('%Y-%m-%d')
                row['period_end'] = datetime.fromtimestamp(row['period_end']).strftime('%Y-%m-%d')
                row['total_size'] = round(row['total_size'] / 1024**3, 2)
                row = {k: '' if v is None else v for k, v in row.items()}
                report_content.append(fstring.format(*row.values()))
            except Exception as e:
                print(dict(row))
                print(e)

        # Render the README template
        env = Environment(loader=FileSystemLoader('.'))
        template = env.get_template('REPORT.md.j2')
        template_data = {}
        if not storage_backend:
            template_data['backend_details'] = f'Backend ID: {args.backend_id} (unknown type)'
        else:
            template_data['backend_details'] = f'Backend ID: {args.backend_id} ({storage_backend.type}, label "{storage_backend.notes}")'
        template_data['total_records'] = sum([row['total_records'] for row in deployment_stats])
        template_data['total_size'] = format_size(sum([row['total_size'] for row in deployment_stats]), 4)
        template_data['unique_nodes'] = len(set([row['node_label'] for row in deployment_stats]))
        template_data['unique_deployments'] = len(set([row['deployment_id'] for row in deployment_stats]))
        count_by_file_type = {k: sum([row['total_records'] for row in deployment_stats if row['file_type'] == k]) for k in set([row['file_type'] for row in deployment_stats])}
        filesize_by_file_type = {k: sum([row['total_size'] for row in deployment_stats if row['file_type'] == k]) for k in set([row['file_type'] for row in deployment_stats])}
        type_counts = []
        type_filesizes = []
        if 'image' in count_by_file_type:
            type_counts.append(f"{count_by_file_type['image']} images")
            type_filesizes.append(f"{round(filesize_by_file_type['image'] / 1024**3, 2)} GiB images")
        if 'audio' in count_by_file_type:
            type_counts.append(f"{count_by_file_type['audio']} audio recordings")
            type_filesizes.append(f"{round(filesize_by_file_type['audio'] / 1024**3, 2)} GiB audio")
        template_data['type_counts'] = ', '.join(type_counts)
        template_data['type_filesizes'] = ', '.join(type_filesizes)

        template_data['created_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        template_data['report'] = '\n'.join(report_content)
        report = template.render(template_data)
        with open(readme_file_path, 'w') as file:
            file.write(report)
        print(f'report written to {readme_file_path}')

if __name__ == '__main__':
    main()
