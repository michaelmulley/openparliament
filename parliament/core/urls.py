from django.conf.urls.defaults import *
from parliament.core.views import PoliticianFeed
urlpatterns = patterns('parliament.core.views',
    (r'^dupes/$', 'dupes'),
    (r'^search/', 'tmpsearch'),
    (r'^politician/(?P<pol_id>\d+)/$', 'politician'),
    url(r'^politician/(?P<pol_id>\d+)/rss/$', PoliticianFeed(), name="politician_feed"),
)