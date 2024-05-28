from django.urls import re_path

from parliament.bills.views import votes_for_session, vote_pk_redirect, ballots, vote

urlpatterns = [
    re_path(r'^$', votes_for_session, name='votes'),
    re_path(r'^(?:session/)?(?P<session_id>\d+-\d)/$', votes_for_session, name='votes_for_session'),
    re_path(r'^(?P<session_id>\d+-\d)/(?P<number>\d+)/$', vote, name='vote'),
    re_path(r'^(?P<vote_id>\d+)/$', vote_pk_redirect),
    re_path(r'^ballots/$', ballots, name='vote_ballots'),
]
