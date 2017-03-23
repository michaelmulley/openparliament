from django.conf.urls import url
from parliament.politicians.views import *

urlpatterns = [
    url(r'^(?P<pol_id>\d+)/rss/statements/$', politician_statement_feed, name="politician_statement_feed"),
    url(r'^(?P<pol_id>\d+)/rss/activity/$', PoliticianActivityFeed(), name="politician_activity_feed"),
    url(r'^$', current_mps, name='politicians'),
    url(r'^former/$', former_mps, name='former_mps'),
    url(r'^autocomplete/$', politician_autocomplete),
    url(r'^memberships/$', PoliticianMembershipListView.as_view(), name='politician_membership_list'),
    url(r'^memberships/(?P<member_id>\d+)/$', PoliticianMembershipView.as_view(), name='politician_membership'),
    url(r'^(?P<pol_slug>[a-z-]+)/$', politician, name='politician'),
    url(r'^(?P<pol_id>\d+)/$', politician, name='politician'),
    url(r'^(?P<pol_slug>[a-z-]+)/contact/$', contact, name='politician_contact'),
    url(r'^(?P<pol_id>\d+)/contact/$', contact, name='politician_contact'),
    url(r'^(?P<pol_slug>[a-z-]+)/text-analysis/$', analysis),
    url(r'^(?P<pol_id>\d+)/text-analysis/$', analysis),
    url(r'^internal/hide_activity/$', hide_activity, name='hide_politician_activity'),
]
