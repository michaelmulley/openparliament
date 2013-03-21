from django.conf.urls import *
from parliament.politicians.views import *

urlpatterns = patterns('parliament.politicians.views',
    url(r'^(?P<pol_id>\d+)/rss/statements/$', 'politician_statement_feed', name="politician_statement_feed"),
    url(r'^(?P<pol_id>\d+)/rss/activity/$', PoliticianActivityFeed(), name="politician_activity_feed"),
    (r'^$', 'current_mps'),
    (r'^former/$', 'former_mps'),
    (r'^autocomplete/$', 'politician_autocomplete'),
    url(r'^roles/$', PoliticianRoleListView.as_view(), name='politician_role_list'),
    url(r'^roles/(?P<member_id>\d+)/$', PoliticianRoleView.as_view(), name='politician_role'),
    (r'^(?P<pol_slug>[a-z-]+)/$', 'politician'),
    (r'^(?P<pol_id>\d+)/$', 'politician'),
    (r'^(?P<pol_slug>[a-z-]+)/contact/$', 'contact'),
    (r'^(?P<pol_id>\d+)/contact/$', 'contact'),
    (r'^internal/hide_activity/$', 'hide_activity'),
)