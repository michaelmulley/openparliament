from django.conf.urls.defaults import *

from parliament.bills.views import BillFeed, BillListFeed

urlpatterns = patterns('parliament.bills.views',
    url(r'^(?P<session_id>\d+-\d)/(?P<bill_number>[CS]-[0-9A-Z]+)/$', 'bill', name='bill'),
    url(r'^(?P<bill_id>\d+)/rss/$', BillFeed(), name='bill_feed'),
    (r'^(?:session/)?(?P<session_id>\d+-\d)/$', 'bills_for_session'),
    url(r'^votes/$', 'votes_for_session', name='votes'),
    (r'^votes/(?:session/)?(?P<session_id>\d+-\d)/$', 'votes_for_session'),
    url(r'^votes/(?P<session_id>\d+-\d)/(?P<number>\d+)/$', 'vote', name='vote'),
    url(r'^$', 'index', name='bills'),
    (r'^(?P<bill_id>\d+)/$', 'bill_pk_redirect'),
    (r'^votes/(?P<vote_id>\d+)/$', 'vote_pk_redirect'),
    url(r'^rss/$', BillListFeed(), name='bill_list_feed'),
)