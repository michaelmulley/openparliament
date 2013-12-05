from django.conf.urls import patterns, url
urlpatterns = patterns('parliament.api.views',
    url(r'^hansards/(?P<hansard_id>\d+)/$', 'hansard', name='legacy_api_hansard'),
    url(r'^hansards/$', 'hansard_list', name='legacy_api_hansard_list'),   
)