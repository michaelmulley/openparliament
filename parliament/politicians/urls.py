from django.urls import re_path
from parliament.politicians.views import *

urlpatterns = [
    re_path(r'^(?P<pol_id>\d+)/rss/statements/$', politician_statement_feed, name="politician_statement_feed"),
    re_path(r'^(?P<pol_id>\d+)/rss/activity/$', PoliticianActivityFeed(), name="politician_activity_feed"),
    re_path(r'^$', current_mps, name='politicians'),
    re_path(r'^former/$', former_mps, name='former_mps'),
    re_path(r'^autocomplete/$', politician_autocomplete),
    re_path(r'^memberships/$', PoliticianMembershipListView.as_view(), name='politician_membership_list'),
    re_path(r'^memberships/(?P<member_id>\d+)/$', PoliticianMembershipView.as_view(), name='politician_membership'),
    re_path(r'^(?P<pol_slug>[a-z-]+)/$', politician, name='politician'),
    re_path(r'^(?P<pol_id>\d+)/$', politician, name='politician'),
    re_path(r'^(?P<pol_slug>[a-z-]+)/contact/$', contact, name='politician_contact'),
    re_path(r'^(?P<pol_id>\d+)/contact/$', contact, name='politician_contact'),
    re_path(r'^(?P<pol_slug>[a-z-]+)/text-analysis/$', analysis),
    re_path(r'^(?P<pol_id>\d+)/text-analysis/$', analysis),
    re_path(r'^internal/hide_activity/$', hide_activity, name='hide_politician_activity'),
]
