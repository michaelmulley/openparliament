from django.conf.urls.defaults import *
urlpatterns = patterns('parliament.hansards.views',
    (r'^hansard/(\d+)/$', 'hansard'),
    (r'^hansard/(\d+)/local/$', 'hansardcache'),
)