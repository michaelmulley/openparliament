from django.conf.urls.defaults import *

from parliament.core.utils import redir_view

urlpatterns = patterns('parliament.hansards.redirect_views',
#    (r'^$', 'index'),
#    (r'^year/(?P<year>\d{4})/$', 'by_year'),
    url(r'^(?P<hansard_id>\d+)/$', 'hansard_redirect'),
#    url(r'^(?P<hansard_date>[0-9-]+)/$', 'hansard', name="debate"),
    url(r'^(?P<hansard_id>\d+)/(?P<sequence>\d+)/$', 'hansard_redirect'),
#    url(r'^(?P<hansard_date>[0-9-]+)/(?P<sequence>\d+)/$', 'hansard', name="debate"),
#    (r'^(?P<hansard_id>\d+)/(?P<sequence>\d+)/twitter/$', 'statement_twitter'),
#    url(r'^(?P<hansard_id>\d+)/(?P<sequence>\d+)/only/$', 'statement_permalink', name="hansard_statement_only"),
#    url(r'^(?P<hansard_date>[0-9-]+)/(?P<sequence>\d+)/only/$', 'statement_permalink', name="hansard_statement_only_bydate"),
)