from django.urls import re_path

from parliament.accounts.google import GoogleLoginEndpointView
from parliament.accounts.views import current_account, token_login, create_token, logout
from parliament.core.views import disable_on_readonly_db

urlpatterns = [
    re_path(r'^email_token/$', create_token),
    re_path(r'^login/(?P<token>.+)$', token_login, name='token_login'),
    re_path(r'^logout/$', logout),
    re_path(r'^google/login/$', disable_on_readonly_db(GoogleLoginEndpointView.as_view())),
    re_path(r'^current/$', current_account),
]
