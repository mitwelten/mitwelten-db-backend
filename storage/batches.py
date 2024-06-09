

batches = [
    '''
    select f.file_id, object_name from prod.files_image f
    join prod.mm_files_image_storage mfs on f.file_id = mfs.file_id
    where mfs.storage_id in (%s, %s) and f.deployment_id in (1198, 1203, 1215, 1224, 2150)
    group by f.file_id
    having count(distinct mfs.storage_id) = 1;
    '''
]
