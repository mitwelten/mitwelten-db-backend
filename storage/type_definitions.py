
class FileType(object):

    group = None
    'image, audio or note'

    identifier = None
    '0 = original, 1 = compressed, etc.'

    extension = None
    'file extension, e.g. jpg, mp3, txt'

    format_name = None
    'WEBP, FLAC, TXT, etc.'

    mime_type = None
    'image/webp, audio/flac, text/plain, etc.'

    description = None

    def __init__(self):
        self.group = None
        self.identifier = None
        self.extension = None
        self.format_name = None
        self.mime_type = None
        self.description = None

class ImageFileType(FileType):

    dimensions = None
    'pixel dimensions, width x height'

    def __init__(self):
        self.group = 'image'
        self.dimensions = None

image_types = [
    ImageFileType(identifier=0, extension='jpg', format_name='JPEG', mime_type='image/jpeg', description='Original uncompressed image'),
    ImageFileType(identifier=1, dimensions=(1920, 1440), extension='webp', format_name='WEBP', mime_type='image/webp', description='Scaled and compressed image - lossy'),
    ImageFileType(identifier=2, extension='gz', format_name='GZIP', mime_type='application/gzip', description='Compressed image - lossless'),
]

audio_types = [
    FileType(group='audio', identifier=0, extension='wav', format_name='Linear PCM', mime_type='audio/wav', description='Original uncompressed audio'),
    FileType(group='audio', identifier=1, extension='flac', format_name='FLAC', mime_type='audio/flac', description='Compressed audio - lossy'),
    FileType(group='audio', identifier=2, extension='gz', format_name='GZIP', mime_type='application/gzip', description='Compressed audio - lossless'),
]

note_types = [
    FileType(group='note', identifier=0, extension='txt', format_name='Plain Text', mime_type='text/plain', description='Original text'),
    FileType(group='note', identifier=1, extension='gz', format_name='GZIP', mime_type='application/gzip', description='Compressed text'),
]
