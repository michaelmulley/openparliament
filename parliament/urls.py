from django.conf.urls.defaults import *
from django.conf import settings
from django.contrib import admin
admin.autodiscover()

from parliament.core.sitemap import sitemaps
from parliament.core.views import SiteNewsFeed

urlpatterns = patterns('',
    (r'^search/', include('parliament.search.urls')),
    (r'^debates/', include('parliament.hansards.urls')),
    url(r'^documents/(?P<document_id>\d+)/$', 'parliament.hansards.views.document_redirect', name='document_redirect'),
    url(r'^documents/(?P<document_id>\d+)/(?P<slug>[a-zA-Z0-9-]+)/$', 'parliament.hansards.views.document_redirect', name='document_redirect'),
    (r'^politicians/', include('parliament.politicians.urls')),
    (r'^bills/', include('parliament.bills.urls')),
    (r'^alerts/', include('parliament.alerts.urls')),
    (r'^committees/', include('parliament.committees.urls')),
    url(r'^speeches/', 'parliament.hansards.views.speeches', name='speeches'),
    #url(r'^about/$', 'django.views.generic.simple.direct_to_template', {'template': 'about/about.html'}, name='about'),
    (r'^api/', include('parliament.api.urls')),
    (r'^accounts/', include('parliament.accounts.urls')),
    (r'^$', 'parliament.core.views.home'),
    (r'^sitemap\.xml$', 'django.contrib.sitemaps.views.sitemap', {'sitemaps': sitemaps}),
    url(r'^sitenews/rss/$', SiteNewsFeed(), name='sitenews_feed'),
    (r'', include('parliament.legacy_urls')),
)

if settings.DEBUG:
    urlpatterns += patterns('',
        (r'^admin/', include(admin.site.urls)),
        (r'^static/(?P<path>.*)$', 'django.views.static.serve',
                {'document_root': settings.MEDIA_ROOT}),
    )

if getattr(settings, 'ADMIN_URL', False):
    urlpatterns += patterns('',
        (settings.ADMIN_URL, include(admin.site.urls)),
        (r'^memcached-status/$', 'parliament.core.maint.memcached_status'),
    )
    
if getattr(settings, 'PARLIAMENT_SITE_CLOSED', False):
    urlpatterns = patterns('',
        (r'.*', 'parliament.core.views.closed')
    ) + urlpatterns
    
if getattr(settings, 'EXTRA_URLS', False):
    urlpatterns += patterns('', *settings.EXTRA_URLS)
    
handler500 = 'parliament.core.errors.server_error'