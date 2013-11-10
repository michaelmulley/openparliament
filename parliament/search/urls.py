from django.conf.urls import patterns, include, url

from parliament.search.views import SearchFeed

urlpatterns = patterns('parliament.search.views',
    url(r'^$', 'search', name='search'),
    url(r'^feed/$', SearchFeed(), name='search_feed'),
)