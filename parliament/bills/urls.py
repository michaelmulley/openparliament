from django.conf.urls import url
from django.core import urlresolvers
from django.http import HttpResponsePermanentRedirect

from parliament.bills.views import BillFeed, BillListFeed, bill, bills_for_session, index, bill_pk_redirect

urlpatterns = [
    url(r'^(?P<session_id>\d+-\d)/(?P<bill_number>[CS]-[0-9A-Z]+)/$', bill, name='bill'),
    url(r'^(?P<bill_id>\d+)/rss/$', BillFeed(), name='bill_feed'),
    url(r'^(?:session/)?(?P<session_id>\d+-\d)/$', bills_for_session, name='bills_for_session'),
    url(r'^$', index, name='bills'),
    url(r'^(?P<bill_id>\d+)/$', bill_pk_redirect),
    url(r'^rss/$', BillListFeed(), name='bill_list_feed'),
    url(r'^votes/([0-9/-]*)$', lambda r, u: HttpResponsePermanentRedirect(
        urlresolvers.reverse('votes') + u)),
]
