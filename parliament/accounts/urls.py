from django.conf.urls.defaults import *

from parliament.accounts.persona import *

urlpatterns = patterns('parliament.accounts.views',
    url(r'^login/$', PersonaLoginEndpointView.as_view()),
    url(r'^logout/$', PersonaLogoutEndpointView.as_view()),
    url(r'^current/$', 'current_account'),
)
