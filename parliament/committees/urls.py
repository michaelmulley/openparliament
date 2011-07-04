from django.conf.urls.defaults import *

urlpatterns = patterns('parliament.committees.views',
    url(r'^$', 'committee_list', name='committee_list'),
    (r'^(?P<committee_id>\d+)/', 'committee_id_redirect'),
    (r'^(?P<slug>[^/]+)/$', 'committee'),
    url(r'^(?P<committee_slug>[^/]+)/(?P<session_id>\d+-\d)/(?P<number>\d+)/$', 'committee_meeting', name='committee_meeting'),
    url(r'^(?P<committee_slug>[^/]+)/(?P<session_id>\d+-\d)/(?P<number>\d+)/(?P<sequence>\d+)/$', 'committee_meeting', name='committee_meeting'),
)