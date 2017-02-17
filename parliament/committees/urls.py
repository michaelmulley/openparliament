from django.conf.urls import url

from parliament.committees.views import *

urlpatterns = [
    url(r'^$', committee_list, name='committee_list'),
    url(r'^activities/(?P<activity_id>\d+)/$', committee_activity, name='committee_activity'),
    url(r'^meetings/$', CommitteeMeetingListView.as_view(), name='committee_meetings'),
    url(r'^(?P<slug>[^/]+)/(?P<year>2\d\d\d)/$', committee_year_archive, name='committee_year_archive'),
    url(r'^(?P<committee_slug>[^/]+)/(?P<session_id>\d+-\d)/(?P<number>\d+)/$', committee_meeting, name='committee_meeting'),
    url(r'^(?P<committee_slug>[^/]+)/(?P<session_id>\d+-\d)/(?P<number>\d+)/text-analysis/$', evidence_analysis),
    url(r'^(?P<committee_slug>[^/]+)/(?P<session_id>\d+-\d)/(?P<number>\d+)/(?P<slug>[a-zA-Z0-9-]+)/$', committee_meeting_statement, name='committee_meeting'),
    url(r'^(?P<committee_slug>[^/]+)/(?P<session_id>\d+-\d)/(?P<number>\d+)/(?P<slug>[a-zA-Z0-9-]+)/only/$', evidence_permalink, name='evidence_permalink'),
    url(r'^(?P<committee_id>\d+)/', committee_id_redirect),
    url(r'^(?P<slug>[^/]+)/$', committee, name='committee'),
    url(r'^(?P<committee_slug>[^/]+)/analysis/$', CommitteeAnalysisView.as_view(), name='committee_analysis'),
]
