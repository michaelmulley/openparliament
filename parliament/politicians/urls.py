from django.conf.urls.defaults import *
from parliament.politicians.views import PoliticianFeed

urlpatterns = patterns('parliament.politicians.views',
    (r'^(?P<pol_id>\d+)/$', 'politician'),
    url(r'^(?P<pol_id>\d+)/rss/$', PoliticianFeed(), name="politician_feed"),
    (r'^$', 'current_mps'),
)