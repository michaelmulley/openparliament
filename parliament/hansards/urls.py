from django.conf.urls.defaults import *

from parliament.core.utils import redir_view

urlpatterns = patterns('parliament.hansards.views',
    (r'^$', 'index'),
    (r'^year/(?P<year>\d{4})/$', 'by_year'),
    (r'^(?P<hansard_id>\d+)/$', 'hansard'),
    (r'^(?P<hansard_id>\d+)/(?P<statement_seq>\d+)/$', 'hansard'),
    (r'^(?P<hansard_id>\d+)/(?P<statement_seq>\d+)/twitter/$', 'statement_twitter'),
    (r'^(?P<hansard_id>\d+)/(?P<statement_seq>\d+)/only/$', 'statement_permalink'),
    (r'^hansard/(\d+)/local/$', 'hansardcache'),
    (r'^(?P<hansard_id>\d+)/(?P<statement_seq>\d+)/permalink/$', redir_view('parliament.hansards.views.statement_permalink')),
)