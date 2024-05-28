# A hack used to coax django-compressor to properly generate bundles
from .default_settings import *

DEBUG = False
COMPRESS_ENABLED = True
COMPRESS_OFFLINE = True

SECRET_KEY = 'compression!'
