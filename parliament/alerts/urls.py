from django.conf.urls import url

from parliament.alerts.views import (politician_hansard_signup, unsubscribe,
    alerts_list, create_alert, modify_alert, politician_hansard_subscribe)

urlpatterns = [
    url(r'^pol_hansard_signup/$', politician_hansard_signup, name='alerts_pol_signup'),
    url(r'^unsubscribe/(?P<key>[^\s/]+)/$', unsubscribe, name='alerts_unsubscribe'),
    url(r'^$', alerts_list, name='alerts_list'),
    url(r'^create/$', create_alert),
    url(r'^(?P<subscription_id>\d+)/$', modify_alert),
    url(r'^pha/(?P<signed_key>[^\s/]+)$', politician_hansard_subscribe, name='alerts_pol_subscribe'),
]
