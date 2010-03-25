from django.conf.urls.defaults import *
urlpatterns = patterns('parliament.core.views',
    (r'^dupes/$', 'dupes'),
    (r'^search/', 'tmpsearch'),
    (r'^politician/(?P<pol_id>\d+)/$', 'politician'),
)