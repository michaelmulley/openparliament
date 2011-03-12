from django.conf.urls.defaults import *

urlpatterns = patterns('parliament.api.handlers',
    (r'^hansards/(?P<hansard_id>\d+)/$', 'hansard_resource'),
    (r'^hansards/$', 'hansardlist_resource'),
    (r'^beta/politicians/(?P<politician_id>\d+)/$', 'politician_resource'),
    (r'^beta/politicians/hoc_id/(?P<callback_id>\d+)/$', 'politician_resource'),
)