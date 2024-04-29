from django.urls import re_path

from parliament.core.utils import redir_view
from parliament.hansards.redirect_views import hansard_redirect

urlpatterns = [
    re_path(r'^hansards/$', redir_view('debates')),
    re_path(r'^hansards/year/(?P<year>\d{4})/$', redir_view('debates_by_year')),
    re_path(r'^hansards/(?P<hansard_id>\d+)/$', hansard_redirect),
    re_path(r'^hansards/(?P<hansard_date>[0-9-]+)/$', hansard_redirect),
    re_path(r'^hansards/(?P<hansard_id>\d+)/(?P<sequence>\d+)/$', hansard_redirect),
    re_path(r'^hansards/(?P<hansard_date>[0-9-]+)/(?P<sequence>\d+)/$', hansard_redirect),
    re_path(r'^hansards/(?P<hansard_id>\d+)/(?P<sequence>\d+)/(?P<only>only|permalink)/$', hansard_redirect),
    re_path(r'^hansards/(?P<hansard_date>[0-9-]+)/(?P<sequence>\d+)/(?P<only>only|permalink)/$', hansard_redirect),
]
