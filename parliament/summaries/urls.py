from django.urls import path

from .views import summary_feedback, summary_poll

urlpatterns = [
    path('poll/', summary_poll, name='summary_poll'),
    path('feedback/', summary_feedback, name='summary_feedback'),
]
