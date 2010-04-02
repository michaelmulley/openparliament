from django.conf.urls.defaults import *

urlpatterns = patterns('parliament.bills.views',
    (r'^(?P<bill_id>\d+)/$', 'bill'),
    (r'^session/(?P<session_id>\d+)/$', 'bills_for_session'),
    (r'^votes/session/(?P<session_id>\d+)/$', 'votes_for_session'),
    (r'^votes/(?P<vote_id>\d+)/$', 'vote'),
    (r'^$', 'index'),
)