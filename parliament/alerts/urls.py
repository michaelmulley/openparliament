from django.conf.urls.defaults import *

urlpatterns = patterns('parliament.alerts.views',
    url(r'^pol_hansard_signup/$', 'politician_hansard_signup', name='alerts_pol_signup'),
    url(r'^unsubscribe/(?P<key>[^\s/]+)/$', 'unsubscribe', name='alerts_unsubscribe'),
    (r'^remove/(?P<alert_id>\d+)/(?P<key>.+)$', 'unsubscribe_old'),
    url(r'^$', 'alerts_list', name='alerts_list'),
    url(r'^create/$', 'create_alert'),
    url(r'^(?P<subscription_id>\d+)/$', 'modify_alert'),
    url(r'^pha/(?P<signed_key>[^\s/]+)$', 'politician_hansard_subscribe', name='alerts_pol_subscribe'),
)
