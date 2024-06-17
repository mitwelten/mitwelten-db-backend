

batches = [
    '''
    select f.file_id, object_name from prod.files_image f
    join prod.mm_files_image_storage mfs on f.file_id = mfs.file_id
    where mfs.storage_id in (%s, %s) and f.deployment_id in (1198, 1203, 1215, 1224, 2150)
    group by f.file_id
    having count(distinct mfs.storage_id) = 1;
    ''',
    '''
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
]
