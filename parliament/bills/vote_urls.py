from django.conf.urls import *

urlpatterns = patterns('parliament.bills.views',
    url(r'^$', 'votes_for_session', name='votes'),
    (r'^(?:session/)?(?P<session_id>\d+-\d)/$', 'votes_for_session'),
    url(r'^(?P<session_id>\d+-\d)/(?P<number>\d+)/$', 'vote', name='vote'),
    (r'^(?P<vote_id>\d+)/$', 'vote_pk_redirect'),
    url(r'^ballots/$', 'ballots', name='vote_ballots'),
)