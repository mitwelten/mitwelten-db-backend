
from dataclasses import dataclass

@dataclass
class FileType(object):

    identifier: int
    '0 = original, 1 = compressed, etc.'

    extension: str
    'file extension, e.g. jpg, mp3, txt'

    format_name: str
    'WEBP, FLAC, TXT, etc.'

    mime_type: str
    'image/webp, audio/flac, text/plain, etc.'

    description: str

    group: str
    'image, audio or note'

@dataclass
class ImageFileType(FileType):

    dimensions: tuple = None
    'pixel dimensions, width x height'

    group: str = 'image'

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
