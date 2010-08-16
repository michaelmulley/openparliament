from django.conf.urls.defaults import *

from parliament.core.utils import redir_view

urlpatterns = patterns('parliament.hansards.views',
    (r'^$', 'index'),
    (r'^year/(?P<year>\d{4})/$', 'by_year'),
    url(r'^(?P<hansard_id>\d+)/$', 'hansard', name="hansard"),
    url(r'^(?P<hansard_date>[0-9-]+)/$', 'hansard', name="hansard_bydate"),
    url(r'^(?P<hansard_id>\d+)/(?P<statement_seq>\d+)/$', 'hansard', name="hansard_statement"),
    url(r'^(?P<hansard_date>[0-9-]+)/(?P<statement_seq>\d+)/$', 'hansard', name="hansard_statement_bydate"),
    (r'^(?P<hansard_id>\d+)/(?P<statement_seq>\d+)/twitter/$', 'statement_twitter'),
    url(r'^(?P<hansard_id>\d+)/(?P<statement_seq>\d+)/only/$', 'statement_permalink', name="hansard_statement_only"),
    url(r'^(?P<hansard_date>[0-9-]+)/(?P<statement_seq>\d+)/only/$', 'statement_permalink', name="hansard_statement_only_bydate"),
    (r'^hansard/(\d+)/local/$', 'hansardcache'),
    (r'^(?P<hansard_id>\d+)/(?P<statement_seq>\d+)/permalink/$', redir_view('parliament.hansards.views.statement_permalink')),
)