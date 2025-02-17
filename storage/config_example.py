import sys
sys.path.append('../')

import credentials as crd

class LocalStorageDefaults(object):
    '''
    Default values specific to this instance/machine for local storage backend.

    Use this to define how and where local storage backends should be created.
    '''

    title = None
    created_at = None
    original_path = None
    priority = None
    storage_id = None
    dot_file_name = None
    storage_dir = None
    device_label = None

    def __init__(self):
        self.title = 'Mitwelten Storage Backend'
        self.created_at = None
        self.original_path = None
        self.priority = 2
        self.storage_id = None
        self.dot_file_name  = '.mitwelten-storage-id'
        self.storage_dir = 'archive'
        self.device_label = None

mc_aliases = {
    's3.server1.com': 's1',
    's3.server2.com': 's2',
    's3.server3.com': 's3',
}
'''hostname aliases for use with mc cli'''
