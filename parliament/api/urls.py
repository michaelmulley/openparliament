from django.urls import re_path

from parliament.api.views import hansard, hansard_list

urlpatterns = [
    re_path(r'^hansards/(?P<hansard_id>\d+)/$', hansard, name='legacy_api_hansard'),
    re_path(r'^hansards/$', hansard_list, name='legacy_api_hansard_list'),   
]