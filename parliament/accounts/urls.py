from django.conf.urls.defaults import *

from parliament.accounts.persona import *

urlpatterns = patterns('',
	url(r'^login/$', PersonaLoginEndpointView.as_view()),
	url(r'^logout/$', PersonaLogoutEndpointView.as_view()),
)