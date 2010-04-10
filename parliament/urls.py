from django.conf.urls.defaults import *
from django.conf import settings
from django.contrib import admin, databrowse
admin.autodiscover()

from parliament.core.sitemap import sitemaps

urlpatterns = patterns('',
    (r'^search/', include('parliament.search.urls')),
    (r'^hansards/', include('parliament.hansards.urls')),
    (r'^politicians/', include('parliament.politicians.urls')),
    (r'^bills/', include('parliament.bills.urls')),
    #url(r'^about/$', 'django.views.generic.simple.direct_to_template', {'template': 'about/about.html'}, name='about'),
    (r'^api/', include('parliament.api.urls')),
    (r'^$', 'parliament.core.views.home'),
    #(r'^$', 'django.views.generic.simple.direct_to_template', {'template': 'teaser.html'}),
    (r'^sitemap\.xml$', 'django.contrib.sitemaps.views.sitemap', {'sitemaps': sitemaps}),
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