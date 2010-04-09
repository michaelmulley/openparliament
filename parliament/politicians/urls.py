from django.conf.urls.defaults import *
from parliament.politicians.views import PoliticianActivityFeed, PoliticianStatementFeed

urlpatterns = patterns('parliament.politicians.views',
    (r'^(?P<pol_id>\d+)/$', 'politician'),
    url(r'^(?P<pol_id>\d+)/rss/statements/$', PoliticianStatementFeed(), name="politician_statement_feed"),
    url(r'^(?P<pol_id>\d+)/rss/activity/$', PoliticianActivityFeed(), name="politician_activity_feed"),
    (r'^$', 'current_mps'),
    (r'^former/$', 'former_mps'),
)