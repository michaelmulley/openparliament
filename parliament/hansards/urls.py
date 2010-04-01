from django.conf.urls.defaults import *
urlpatterns = patterns('parliament.hansards.views',
    (r'^$', 'index'),
    (r'^year/(?P<year>\d{4})/$', 'by_year'),
    (r'^(\d+)/$', 'hansard'),
    (r'^hansard/(\d+)/local/$', 'hansardcache'),
)