from django.conf.urls.defaults import *
urlpatterns = patterns('parliament.hansards.views',
    (r'^$', 'index'),
    (r'^year/(?P<year>\d{4})/$', 'by_year'),
    (r'^(?P<hansard_id>\d+)/$', 'hansard'),
    (r'^(?P<hansard_id>\d+)/(?P<statement_seq>\d+)/$', 'hansard'),
    (r'^(?P<hansard_id>\d+)/(?P<statement_seq>\d+)/twitter/$', 'statement_twitter'),
    (r'^(?P<hansard_id>\d+)/(?P<statement_seq>\d+)/permalink/$', 'statement_permalink'),
    (r'^hansard/(\d+)/local/$', 'hansardcache'),
)