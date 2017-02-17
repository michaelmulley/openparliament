from django.conf.urls import url

from parliament.search.views import SearchFeed, search

urlpatterns = [
    url(r'^$', search, name='search'),
    url(r'^feed/$', SearchFeed(), name='search_feed'),
]
