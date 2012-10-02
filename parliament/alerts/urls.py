from django.conf.urls.defaults import *

urlpatterns = patterns('parliament.alerts.views',
    (r'^signup/$', 'signup'),
    url(r'^unsubscribe/(?P<key>[^\s/]+)/$', 'unsubscribe', name='alerts_unsubscribe'),
    (r'^activate/(?P<alert_id>\d+)/(?P<key>.+)$', 'activate'),
    (r'^remove/(?P<alert_id>\d+)/(?P<key>.+)$', 'unsubscribe_old'),
    url(r'^$', 'alerts_list', name='alerts_list'),
    url(r'^create/$', 'create_alert'),
    url(r'^(?P<subscription_id>\d+)/$', 'modify_alert'),
)