from django.conf.urls import url

from parliament.bills.views import votes_for_session, vote_pk_redirect, ballots, vote

urlpatterns = [
    url(r'^$', votes_for_session, name='votes'),
    url(r'^(?:session/)?(?P<session_id>\d+-\d)/$', votes_for_session, name='votes_for_session'),
    url(r'^(?P<session_id>\d+-\d)/(?P<number>\d+)/$', vote, name='vote'),
    url(r'^(?P<vote_id>\d+)/$', vote_pk_redirect),
    url(r'^ballots/$', ballots, name='vote_ballots'),
]
