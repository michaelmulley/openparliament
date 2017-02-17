from django.conf.urls import url

from parliament.api.views import hansard, hansard_list

urlpatterns = [
    url(r'^hansards/(?P<hansard_id>\d+)/$', hansard, name='legacy_api_hansard'),
    url(r'^hansards/$', hansard_list, name='legacy_api_hansard_list'),   
]