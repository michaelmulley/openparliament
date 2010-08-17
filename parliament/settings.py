# Django settings for parliament project.
import os

DEBUG = False

ADMINS = (
    ('Michael Mulley', 'michael@michaelmulley.com'),
)

MANAGERS = ADMINS

PROJ_ROOT = os.path.dirname(os.path.realpath(__file__))

HAYSTACK_SEARCH_ENGINE = 'solr'
HAYSTACK_SITECONF = 'parliament.search_sites'

CACHE_MIDDLEWARE_KEY_PREFIX = 'parl'

DJANGO_STATIC = True

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'America/Montreal'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale
USE_L10N = True

# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = PROJ_ROOT + '/static/'


# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_URL = '/static/'

DJANGO_STATIC_SAVE_PREFIX = MEDIA_ROOT + 'cacheable/'
DJANGO_STATIC_NAME_PREFIX = 'cacheable/'
DJANGO_STATIC_MEDIA_URL = MEDIA_URL

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/static/admin/'

APPEND_SLASH = False

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
#     'django.template.loaders.eggs.Loader',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.cache.UpdateCacheMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    #'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'debug_toolbar.middleware.DebugToolbarMiddleware',
    'django.contrib.flatpages.middleware.FlatpageFallbackMiddleware',
    'django.middleware.cache.FetchFromCacheMiddleware',
)

ROOT_URLCONF = 'parliament.urls'

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    PROJ_ROOT + "/templates",
)

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.admin',
    'django.contrib.humanize',
    'django.contrib.markup',
    'django.contrib.databrowse',
    'django.contrib.flatpages',
    'django.contrib.sitemaps',
    'django_extensions',
    'haystack',
    'south',
    'sorl.thumbnail',
    'django_static',
    'parliament.core',
    'parliament.hansards',
    'parliament.elections',
    'parliament.financials',
    'parliament.bills',
    'parliament.politicians',
    'parliament.activity',
    'parliament.alerts',
]

THUMBNAIL_SUBDIR = '_thumbs'
THUMBNAIL_PROCESSORS = (
    # Default processors
    'sorl.thumbnail.processors.colorspace',
    'sorl.thumbnail.processors.autocrop',
    'parliament.core.thumbnail.crop_first',
    'sorl.thumbnail.processors.scale_and_crop',
    'sorl.thumbnail.processors.filters',
)

SOUTH_TESTS_MIGRATE = False

from settings_local import *

if 'EXTRA_APPS' in globals():
    INSTALLED_APPS += globals()['EXTRA_APPS']

