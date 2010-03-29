from django.conf.urls.defaults import *

urlpatterns = patterns('parliament.core.views',
    (r'^dupes/$', 'dupes'),
    (r'^search/', 'search'),
)