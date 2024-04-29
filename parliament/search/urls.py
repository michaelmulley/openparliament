from django.urls import re_path

from parliament.search.views import SearchFeed, search

urlpatterns = [
    re_path(r'^$', search, name='search'),
    re_path(r'^feed/$', SearchFeed(), name='search_feed'),
]
