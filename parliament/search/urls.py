from django.conf.urls.defaults import *

from parliament.search.views import SearchFeed

urlpatterns = patterns('parliament.search.views',
    url(r'^$', 'search', name='search'),
    url(r'^feed/$', SearchFeed(), name='search_feed'),
)