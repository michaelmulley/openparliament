from django.conf.urls.defaults import *

urlpatterns = patterns('parliament.alerts.views',
    (r'^signup/$', 'signup'),
    (r'^activate/(?P<alert_id>\d+)/(?P<key>.+)$', 'activate'),
)