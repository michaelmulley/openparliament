from django.conf.urls import url

from parliament.accounts.persona import *
from parliament.accounts.google import GoogleLoginEndpointView
from parliament.accounts.views import current_account

urlpatterns = [
    url(r'^login/$', PersonaLoginEndpointView.as_view()),
    url(r'^logout/$', PersonaLogoutEndpointView.as_view()),
    url(r'^google/login/$', GoogleLoginEndpointView.as_view()),
    url(r'^current/$', current_account),
]
