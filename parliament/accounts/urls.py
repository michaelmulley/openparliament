from django.conf.urls import patterns, include, url

from parliament.accounts.persona import *

urlpatterns = patterns('parliament.accounts.views',
    url(r'^login/$', PersonaLoginEndpointView.as_view()),
    url(r'^logout/$', PersonaLogoutEndpointView.as_view()),
    url(r'^current/$', 'current_account'),
)
