from django.urls import path

from .views import haiku

urlpatterns = [
    path('', haiku),
    path('<int:haiku_id>/', haiku),
]