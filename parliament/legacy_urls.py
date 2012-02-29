from django.conf.urls.defaults import *

from parliament.core.utils import redir_view

urlpatterns = patterns('parliament.hansards.redirect_views',
    (r'^hansards/$', redir_view('parliament.hansards.views.index')),
    (r'^hansards/year/(?P<year>\d{4})/$', redir_view('parliament.hansards.views.by_year')),
    url(r'^hansards/(?P<hansard_id>\d+)/$', 'hansard_redirect'),
    url(r'^hansards/(?P<hansard_date>[0-9-]+)/$', 'hansard_redirect'),
    url(r'^hansards/(?P<hansard_id>\d+)/(?P<sequence>\d+)/$', 'hansard_redirect'),
    url(r'^hansards/(?P<hansard_date>[0-9-]+)/(?P<sequence>\d+)/$', 'hansard_redirect'),
    url(r'^hansards/(?P<hansard_id>\d+)/(?P<sequence>\d+)/(?P<only>only|permalink)/$', 'hansard_redirect'),
    url(r'^hansards/(?P<hansard_date>[0-9-]+)/(?P<sequence>\d+)/(?P<only>only|permalink)/$', 'hansard_redirect'),
)