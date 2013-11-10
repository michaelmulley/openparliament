from django.conf.urls import patterns, include, url
from django.core import urlresolvers
from django.http import HttpResponsePermanentRedirect

from parliament.bills.views import BillFeed, BillListFeed

urlpatterns = patterns('parliament.bills.views',
    url(r'^(?P<session_id>\d+-\d)/(?P<bill_number>[CS]-[0-9A-Z]+)/$', 'bill', name='bill'),
    url(r'^(?P<bill_id>\d+)/rss/$', BillFeed(), name='bill_feed'),
    (r'^(?:session/)?(?P<session_id>\d+-\d)/$', 'bills_for_session'),
    url(r'^$', 'index', name='bills'),
    (r'^(?P<bill_id>\d+)/$', 'bill_pk_redirect'),
    url(r'^rss/$', BillListFeed(), name='bill_list_feed'),
    url(r'^votes/([0-9/-]*)$', lambda r,u: HttpResponsePermanentRedirect(
        urlresolvers.reverse('votes') + u)),
)
