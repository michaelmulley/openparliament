from django.conf.urls.defaults import *
from parliament.politicians.views import PoliticianFeed

urlpatterns = patterns('parliament.politicians.views',
    (r'^politician/(?P<pol_id>\d+)/$', 'politician'),
    url(r'^politician/(?P<pol_id>\d+)/rss/$', PoliticianFeed(), name="politician_feed"),
)