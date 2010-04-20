from django.conf.urls.defaults import *
from django.conf import settings
from django.contrib import admin, databrowse
admin.autodiscover()

from parliament.core.sitemap import sitemaps
from parliament.core.views import SiteNewsFeed

urlpatterns = patterns('',
    (r'^search/', include('parliament.search.urls')),
    (r'^hansards/', include('parliament.hansards.urls')),
    (r'^politicians/', include('parliament.politicians.urls')),
    (r'^bills/', include('parliament.bills.urls')),
    (r'^alerts/', include('parliament.alerts.urls')),
    #url(r'^about/$', 'django.views.generic.simple.direct_to_template', {'template': 'about/about.html'}, name='about'),
    (r'^api/', include('parliament.api.urls')),
    (r'^$', 'parliament.core.views.home'),
    (r'^sitemap\.xml$', 'django.contrib.sitemaps.views.sitemap', {'sitemaps': sitemaps}),
    url(r'^sitenews/rss/$', SiteNewsFeed(), name='sitenews_feed'),
)

if settings.DEBUG:
    urlpatterns += patterns('',
        (r'^databrowse/(.*)', databrowse.site.root),
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
    
handler500 = 'parliament.core.errors.server_error'