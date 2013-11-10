from django.conf.urls import patterns, include, url

urlpatterns = patterns('parliament.api.handlers',
    (r'^hansards/(?P<hansard_id>\d+)/$', 'hansard_resource'),
    (r'^hansards/$', 'hansardlist_resource'),   
)