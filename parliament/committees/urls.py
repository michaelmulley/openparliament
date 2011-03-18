from django.conf.urls.defaults import *

urlpatterns = patterns('parliament.committees.views',
    (r'^$', 'committee_list'),
    (r'^(?P<acronym>[A-Z0-9]{4})/$', 'committee'),
    (r'^(?P<committee_id>\d+)/$', 'committee'),
)