from django.conf.urls import url

from parliament.core.utils import redir_view
from parliament.hansards.redirect_views import hansard_redirect

urlpatterns = [
    url(r'^hansards/$', redir_view('debates')),
    url(r'^hansards/year/(?P<year>\d{4})/$', redir_view('debates_by_year')),
    url(r'^hansards/(?P<hansard_id>\d+)/$', hansard_redirect),
    url(r'^hansards/(?P<hansard_date>[0-9-]+)/$', hansard_redirect),
    url(r'^hansards/(?P<hansard_id>\d+)/(?P<sequence>\d+)/$', hansard_redirect),
    url(r'^hansards/(?P<hansard_date>[0-9-]+)/(?P<sequence>\d+)/$', hansard_redirect),
    url(r'^hansards/(?P<hansard_id>\d+)/(?P<sequence>\d+)/(?P<only>only|permalink)/$', hansard_redirect),
    url(r'^hansards/(?P<hansard_date>[0-9-]+)/(?P<sequence>\d+)/(?P<only>only|permalink)/$', hansard_redirect),
]
