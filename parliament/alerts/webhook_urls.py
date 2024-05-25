from django.urls import path

from parliament.alerts.views import bounce_webhook

urlpatterns = [
	path('', bounce_webhook)
]
