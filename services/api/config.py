import sys
sys.path.append('../')

import credentials as crd

supported_image_formats = {
    'image/png':  'png',
    'image/jpg':  'jpg',
    'image/jpeg': 'jpeg',
    'image/gif':  'gif',
    'image/webp': 'webp',
}

thumbnail_size = (64, 64)
