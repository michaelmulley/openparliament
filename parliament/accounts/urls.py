from django.conf.urls import url

from parliament.accounts.google import GoogleLoginEndpointView
from parliament.accounts.views import current_account, token_login, create_token, logout
from parliament.core.views import disable_on_readonly_db

urlpatterns = [
    url(r'^email_token/$', create_token),
    url(r'^login/(?P<token>.+)$', token_login, name='token_login'),
    url(r'^logout/$', logout),
    url(r'^google/login/$', disable_on_readonly_db(GoogleLoginEndpointView.as_view())),
    url(r'^current/$', current_account),
]
