from django.urls import re_path

from parliament.alerts.views import (politician_hansard_signup, unsubscribe,
    alerts_list, create_alert, modify_alert, politician_hansard_subscribe)

urlpatterns = [
    re_path(r'^pol_hansard_signup/$', politician_hansard_signup, name='alerts_pol_signup'),
    re_path(r'^unsubscribe/(?P<key>[^\s/]+)/$', unsubscribe, name='alerts_unsubscribe'),
    re_path(r'^$', alerts_list, name='alerts_list'),
    re_path(r'^create/$', create_alert),
    re_path(r'^(?P<subscription_id>\d+)/$', modify_alert),
    re_path(r'^pha/(?P<signed_key>[^\s/]+)$', politician_hansard_subscribe, name='alerts_pol_subscribe'),
]
