from django.conf.urls.defaults import *

from parliament.core.utils import redir_view

urlpatterns = patterns('parliament.hansards.views',
    (r'^$', 'index'),
    (r'^year/(?P<year>\d{4})/$', 'by_year'),
    url(r'^(?P<hansard_id>\d+)/$', 'hansard', name="hansard"),
    url(r'^(?P<hansard_date>[0-9-]+)/$', 'hansard', name="debate"),
    url(r'^(?P<hansard_id>\d+)/(?P<sequence>\d+)/$', 'hansard', name="hansard_statement"),
    url(r'^(?P<hansard_date>[0-9-]+)/(?P<sequence>\d+)/$', 'hansard', name="debate"),
    (r'^(?P<hansard_id>\d+)/(?P<sequence>\d+)/twitter/$', 'statement_twitter'),
    url(r'^(?P<hansard_id>\d+)/(?P<sequence>\d+)/only/$', 'statement_permalink', name="hansard_statement_only"),
    url(r'^(?P<hansard_date>[0-9-]+)/(?P<sequence>\d+)/only/$', 'statement_permalink', name="hansard_statement_only_bydate"),
    (r'^(?P<document_id>\d+)/local/(?P<language>en|fr)/$', 'document_cache'),
    (r'^(?P<hansard_id>\d+)/(?P<sequence>\d+)/permalink/$', redir_view('parliament.hansards.views.statement_permalink')),
)