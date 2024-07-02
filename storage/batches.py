
batches = [
    {
        'id': 'batch_0',
        'type': 'image',
        'target': 'Mitwelten 8',
        'description': 'Selection for Mitwelten 8',
        'query': '''
        select f.file_id, object_name from prod.files_image f
        join prod.mm_files_image_storage mfs on f.file_id = mfs.file_id
        where mfs.storage_id in (%s, %s) and f.deployment_id in (1198, 1203, 1215, 1224, 2150)
        group by f.file_id
        having count(distinct mfs.storage_id) = 1
        order by f.deployment_id, f.time;
        '''
    },
    {
        'id': 'batch_1',
        'type': 'image',
        'target': 'mw-archiv-1',
        'description': 'All of FS3, minus the deployments in batch_0, minus 791',
        'query': '''
        -- count 1700849, total size 7170 GB
        with selected_deployments as (
            select d.deployment_id as deployment_id
            from prod.deployments d
            left join prod.mm_tags_deployments mm on mm.deployments_deployment_id = d.deployment_id
            left join prod.tags t on t.tag_id = mm.tags_tag_id
            left join prod.nodes n on d.node_id = n.node_id
            where t.name = 'FS3'
                and n.type = 'Pollinator Cam'
                and d.deployment_id not in (1198, 1203, 1215, 1224, 2150, 791)
        )
        -- select count(*), pg_size_pretty(sum(f.file_size)) from prod.files_image f
        -- where f.deployment_id in (select deployment_id from selected_deployments);
        select f.file_id, object_name from prod.files_image f
        join prod.mm_files_image_storage mfs on f.file_id = mfs.file_id
        where mfs.storage_id in (%s, %s) and f.deployment_id in (select deployment_id from selected_deployments)
        group by f.file_id
        having count(distinct mfs.storage_id) = 1
        order by f.deployment_id, f.time;
        '''
    },
    {
        'id': 'batch_2',
        'type': 'image',
        'target': 'mw-archiv-1',
        'description': 'All of FS1',
        'query': '''
        -- count 459566, total size 2406 GB
        with selected_deployments as (
            select d.deployment_id as deployment_id
            from prod.deployments d
            left join prod.mm_tags_deployments mm on mm.deployments_deployment_id = d.deployment_id
            left join prod.tags t on t.tag_id = mm.tags_tag_id
            left join prod.nodes n on d.node_id = n.node_id
            where t.name = 'FS1'
                and n.type = 'Pollinator Cam'
        )
        -- select count(*), pg_size_pretty(sum(f.file_size)) from prod.files_image f
        -- where f.deployment_id in (select deployment_id from selected_deployments);
        select f.file_id, object_name from prod.files_image f
        join prod.mm_files_image_storage mfs on f.file_id = mfs.file_id
        where mfs.storage_id in (%s, %s) and f.deployment_id in (select deployment_id from selected_deployments)
        group by f.file_id
        having count(distinct mfs.storage_id) = 1
        order by f.deployment_id, f.time;
        '''
    },
    {
        'id': 'batch_3',
        'type': 'image',
        'target': 'mw-archiv-2',
        'description': '9GB of of FS2, minus the deployments above',
        'query': '''
        -- count 1859041, total size 8967 GB
        with selected_deployments as (
            select d.deployment_id as deployment_id
            from prod.deployments d
            left join prod.mm_tags_deployments mm on mm.deployments_deployment_id = d.deployment_id
            left join prod.tags t on t.tag_id = mm.tags_tag_id
            left join prod.nodes n on d.node_id = n.node_id
            where t.name = 'FS2'
                and n.type = 'Pollinator Cam'
                and d.deployment_id in (20,21,22,24,27,31,38,49,53,55,62,67,76,78,81,153)
        )
        -- select count(*), pg_size_pretty(sum(f.file_size)) from prod.files_image f
        -- where f.deployment_id in (select deployment_id from selected_deployments);
        select f.file_id, object_name from prod.files_image f
        join prod.mm_files_image_storage mfs on f.file_id = mfs.file_id
        where mfs.storage_id in (%s, %s) and f.deployment_id in (select deployment_id from selected_deployments)
        group by f.file_id
        having count(distinct mfs.storage_id) = 1
        order by f.deployment_id, f.time;
        '''
    },
    {
        'id': 'batch_4',
        'type': 'image',
        'target': 'mw-archiv-3',
        'description': 'Rest of of batch_3 (FS 2)',
        'query': '''
        -- count 1322837, total size 5051 GB
        with selected_deployments as (
            select d.deployment_id as deployment_id
            from prod.deployments d
            left join prod.mm_tags_deployments mm on mm.deployments_deployment_id = d.deployment_id
            left join prod.tags t on t.tag_id = mm.tags_tag_id
            left join prod.nodes n on d.node_id = n.node_id
            where (t.name = 'FS2'
                and n.type = 'Pollinator Cam'
                and d.deployment_id in (842,846,857,861,883))
                or d.deployment_id = 791
        )
        -- select count(*), pg_size_pretty(sum(f.file_size)) from prod.files_image f
        -- where f.deployment_id in (select deployment_id from selected_deployments);
        select f.file_id, object_name from prod.files_image f
        join prod.mm_files_image_storage mfs on f.file_id = mfs.file_id
        where mfs.storage_id in (%s, %s) and f.deployment_id in (select deployment_id from selected_deployments)
        group by f.file_id
        having count(distinct mfs.storage_id) = 1
        order by f.deployment_id, f.time;
        '''
    },
    {
        'id': 'batch_5',
        'type': 'image',
        'target': '-',
        'description': 'Testing batch',
        'query': '''
        -- batch 5
        select f.file_id, object_name from prod.files_image f
        join prod.mm_files_image_storage mfs on f.file_id = mfs.file_id
        where mfs.storage_id in (%s, %s) and f.deployment_id = 829
        group by f.file_id
        having count(distinct mfs.storage_id) = 1
        limit 42;
        '''
    },
    {
        'id': 'batch_6',
        'type': 'audio',
        'target': 'mw-archiv-4',
        'description': 'All audio files of nodes deployed after 2022-07-01',
        'query': '''
        -- count 1062781, total size 7.81 TB
        -- start lowering the date to get more files if ExtFAT allows
        with selected_deployments as (
            select d.deployment_id as deployment_id
            from prod.deployments d
            where lower(period) > date('2022-07-01')
        )
        -- select count(*), round(sum(file_size)/1024.0/1024.0/1024.0/1024.0, 2) as size_tb
        -- from prod.files_audio f
        -- left join mm_files_audio_storage m on m.file_id = f.file_id
        -- where f.deployment_id in (select deployment_id from selected_deployments)
        --   and m.file_id is not null;
        select f.file_id, object_name from prod.files_audio f
        join prod.mm_files_audio_storage mfs on f.file_id = mfs.file_id
        where mfs.storage_id in (%s, %s) and f.deployment_id in (select deployment_id from selected_deployments)
        group by f.file_id
        having count(distinct mfs.storage_id) = 1
        order by f.deployment_id, f.time;
        '''
    },
    {
        'id': 'batch_7',
        'type': 'image',
        'target': 'mw-archiv-1',
        'description': 'All image files of wild cams and phaeno cams',
        'query': '''
        -- count 35487, total size 69.71 GiB
        with selected_deployments as (
            select d.deployment_id as deployment_id
            from prod.deployments d
            left join prod.nodes n on d.node_id = n.node_id
            where n.type in ('Wild Cam', 'Phaeno Cam')
        )
        select f.file_id, object_name from prod.files_image f
        join prod.mm_files_image_storage mfs on f.file_id = mfs.file_id
        where mfs.storage_id in (%s, %s) and f.deployment_id in (select deployment_id from selected_deployments)
        group by f.file_id
        having count(distinct mfs.storage_id) = 1
        order by f.deployment_id, f.time;
        '''
    },
]
