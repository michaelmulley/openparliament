from django.conf.urls.defaults import *
from django.conf import settings
from django.contrib import admin, databrowse
admin.autodiscover()

urlpatterns = patterns('',

    (r'^core/', include('parliament.core.urls')),
    (r'^hansards/', include('parliament.hansards.urls')),

    # Uncomment the admin/doc line below and add 'django.contrib.admindocs' 
    # to INSTALLED_APPS to enable admin documentation:
    # (r'^admin/doc/', include('django.contrib.admindocs.urls')),
    (r'^admin/', include(admin.site.urls)),
    (r'^$', 'django.views.generic.simple.direct_to_template', {'template': 'teaser.html'}),
)

if settings.DEBUG:
    urlpatterns += patterns('',
        (r'^databrowse/(.*)', databrowse.site.root),
        (r'^static/(?P<path>.*)$', 'django.views.static.serve',
                {'document_root': settings.MEDIA_ROOT}),
    )
