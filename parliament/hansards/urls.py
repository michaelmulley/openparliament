from django.conf.urls.defaults import *
urlpatterns = patterns('parliament.hansards.views',
    (r'^$', 'index'),
    (r'^(?P<year>\d{4})/$', 'by_year'),
    (r'^hansard/(\d+)/$', 'hansard'),
    (r'^hansard/(\d+)/local/$', 'hansardcache'),
)