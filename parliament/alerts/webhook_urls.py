from django.conf.urls import url

from parliament.alerts.views import bounce_webhook

urlpatterns = [
	url(r'', bounce_webhook)
]
