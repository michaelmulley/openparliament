from django.conf.urls.defaults import *

urlpatterns = patterns('parliament.search.views',
    url(r'^$', 'search', name='search'),
)