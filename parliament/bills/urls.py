from django.conf.urls.defaults import *

from parliament.bills.views import BillFeed, BillListFeed

urlpatterns = patterns('parliament.bills.views',
    (r'^(?P<bill_id>\d+)/$', 'bill'),
    url(r'^(?P<bill_id>\d+)/rss/$', BillFeed(), name='bill_feed'),
    (r'^session/(?P<session_id>[\d-]+)/$', 'bills_for_session'),
    (r'^votes/session/(?P<session_id>[\d-]+)/$', 'votes_for_session'),
    (r'^votes/(?P<vote_id>\d+)/$', 'vote'),
    (r'^$', 'index'),
    url(r'^rss/$', BillListFeed(), name='bill_list_feed'),
)