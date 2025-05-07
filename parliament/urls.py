from django.urls import include, path, re_path
from django.conf.urls.static import static
from django.conf import settings
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap as sitemap_view

from parliament.core.api import docs as api_docs
from parliament.core.api import no_robots
from parliament.core.sitemap import sitemaps
from parliament.core.views import SiteNewsFeed, home, closed
from parliament.hansards.views import document_redirect, speeches

urlpatterns = [
    path('search/', include('parliament.search.urls')),
    path('debates/', include('parliament.hansards.urls')),
    re_path(r'documents/(?P<document_id>\d+)/$', document_redirect, name='document_redirect'),
    re_path(r'^documents/(?P<document_id>\d+)/(?P<slug>[a-zA-Z0-9-]+)/$', document_redirect, name='document_redirect'),
    re_path(r'^politicians/', include('parliament.politicians.urls')),
    re_path(r'^bills/', include('parliament.bills.urls')),
    re_path(r'^votes/', include('parliament.bills.vote_urls')),
    re_path(r'^alerts/', include('parliament.alerts.urls')),
    re_path(r'^committees/', include('parliament.committees.urls')),
    re_path(r'^speeches/', speeches, name='speeches'),
    #re_path(r'^about/$', 'django.views.generic.simple.direct_to_template', {'template': 'about/about.html'}, name='about'),
    re_path(r'^api/$', api_docs),
    re_path(r'^api/', include('parliament.api.urls')),
    re_path(r'^accounts/', include('parliament.accounts.urls')),
    path(r'labs/haiku/', include('parliament.haiku.urls')),
    re_path(r'^$', home),
    path('summaries/', include('parliament.summaries.urls')),
    re_path(r'^sitemap\.xml$', sitemap_view, {'sitemaps': sitemaps}),
    re_path(r'^sitenews/rss/$', SiteNewsFeed(), name='sitenews_feed'),
    re_path(r'^robots\.txt$', no_robots),
    re_path(r'', include('parliament.legacy_urls')),
]

if settings.DEBUG:
    if not getattr(settings, 'ADMIN_URL', False):
        urlpatterns += [
            path('admin/', admin.site.urls),
        ]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    if getattr(settings, 'ENABLE_DEBUG_TOOLBAR', False):
        from debug_toolbar.toolbar import debug_toolbar_urls
        urlpatterns += debug_toolbar_urls()

if getattr(settings, 'ADMIN_URL', False):
    urlpatterns += [
        re_path(settings.ADMIN_URL, admin.site.urls)
    ]
    
if getattr(settings, 'PARLIAMENT_SITE_CLOSED', False):
    urlpatterns = [
        re_path(r'.*', closed)
    ] + urlpatterns
    
if getattr(settings, 'EXTRA_URL_INCLUDES', False):
    for url_pattern, url_include in settings.EXTRA_URL_INCLUDES:
        urlpatterns.append(re_path(url_pattern, include(url_include)))
    
handler500 = 'parliament.core.errors.server_error'