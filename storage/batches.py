
# Lost files (during migration from minio to minio3, in December 2023)
# [begin] 0527-0574/2023-10-08/09/0527-0574_2023-10-08T09-56-47Z.jpg
# [end]   0527-0574/2023-10-13/08/0527-0574_2023-10-13T08-06-42Z.jpg

batches = [
    '''
    -- batch 0
    select f.file_id, object_name from prod.files_image f
    join prod.mm_files_image_storage mfs on f.file_id = mfs.file_id
    where mfs.storage_id in (%s, %s) and f.deployment_id in (1198, 1203, 1215, 1224, 2150)
    group by f.file_id
    having count(distinct mfs.storage_id) = 1;
    ''',
    '''
    -- batch 1
    -- All of FS3, minus the deployments above
    -- count 1700849, total size 7170 GB
    with selected_deployments as (
        select d.deployment_id as deployment_id
        from prod.deployments d
        left join prod.mm_tags_deployments mm on mm.deployments_deployment_id = d.deployment_id
        left join prod.tags t on t.tag_id = mm.tags_tag_id
        left join prod.nodes n on d.node_id = n.node_id
        where t.name = 'FS3'
            and n.type = 'Pollinator Cam'
            and d.deployment_id not in (1198, 1203, 1215, 1224, 2150)
    )
    -- select count(*), pg_size_pretty(sum(f.file_size)) from prod.files_image f
    -- where f.deployment_id in (select deployment_id from selected_deployments);
    select f.file_id, object_name from prod.files_image f
    join prod.mm_files_image_storage mfs on f.file_id = mfs.file_id
    where mfs.storage_id in (%s, %s) and f.deployment_id in (select deployment_id from selected_deployments)
    group by f.file_id
    having count(distinct mfs.storage_id) = 1;
    ''',
    '''
    -- batch 2
    -- All of FS1, minus the deployments above
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
    having count(distinct mfs.storage_id) = 1;
    ''',
    '''
    -- batch 3
    -- 9GB of of FS2, minus the deployments above
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
    having count(distinct mfs.storage_id) = 1;
    ''',
    '''
    -- batch 4
    -- rest of of batch 3 (FS 2)
    -- count 1322837, total size 5051 GB
    with selected_deployments as (
        select d.deployment_id as deployment_id
        from prod.deployments d
        left join prod.mm_tags_deployments mm on mm.deployments_deployment_id = d.deployment_id
        left join prod.tags t on t.tag_id = mm.tags_tag_id
        left join prod.nodes n on d.node_id = n.node_id
        where t.name = 'FS2'
            and n.type = 'Pollinator Cam'
            and d.deployment_id in (842,846,857,861,883)
    )
    -- select count(*), pg_size_pretty(sum(f.file_size)) from prod.files_image f
    -- where f.deployment_id in (select deployment_id from selected_deployments);
    select f.file_id, object_name from prod.files_image f
    join prod.mm_files_image_storage mfs on f.file_id = mfs.file_id
    where mfs.storage_id in (%s, %s) and f.deployment_id in (select deployment_id from selected_deployments)
    group by f.file_id
    having count(distinct mfs.storage_id) = 1;
    ''',
]
