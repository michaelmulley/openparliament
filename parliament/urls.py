from django.conf.urls import include, url
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
    url(r'^search/', include('parliament.search.urls')),
    url(r'^debates/', include('parliament.hansards.urls')),
    url(r'^documents/(?P<document_id>\d+)/$', document_redirect, name='document_redirect'),
    url(r'^documents/(?P<document_id>\d+)/(?P<slug>[a-zA-Z0-9-]+)/$', document_redirect, name='document_redirect'),
    url(r'^politicians/', include('parliament.politicians.urls')),
    url(r'^bills/', include('parliament.bills.urls')),
    url(r'^votes/', include('parliament.bills.vote_urls')),
    url(r'^alerts/', include('parliament.alerts.urls')),
    url(r'^committees/', include('parliament.committees.urls')),
    url(r'^speeches/', speeches, name='speeches'),
    #url(r'^about/$', 'django.views.generic.simple.direct_to_template', {'template': 'about/about.html'}, name='about'),
    url(r'^api/$', api_docs),
    url(r'^api/', include('parliament.api.urls')),
    url(r'^accounts/', include('parliament.accounts.urls')),
    url(r'^$', home),
    url(r'^sitemap\.xml$', sitemap_view, {'sitemaps': sitemaps}),
    url(r'^sitenews/rss/$', SiteNewsFeed(), name='sitenews_feed'),
    url(r'^robots\.txt$', no_robots),
    url(r'', include('parliament.legacy_urls')),
]

if settings.DEBUG:
    urlpatterns += [
        url(r'^admin/', include(admin.site.urls)),
    ]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if getattr(settings, 'ADMIN_URL', False):
    urlpatterns += [
        url(settings.ADMIN_URL, include(admin.site.urls))
    ]
    
if getattr(settings, 'PARLIAMENT_SITE_CLOSED', False):
    urlpatterns = [
        url(r'.*', closed)
    ] + urlpatterns
    
if getattr(settings, 'EXTRA_URL_INCLUDES', False):
    for url_pattern, url_include in settings.EXTRA_URL_INCLUDES:
        urlpatterns.append(url(url_pattern, include(url_include)))
    
handler500 = 'parliament.core.errors.server_error'