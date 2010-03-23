from django.conf.urls.defaults import *

from django.contrib import admin, databrowse
admin.autodiscover()

urlpatterns = patterns('',

    (r'^core/', include('parliament.core.urls')),
    (r'^hansards/', include('parliament.hansards.urls')),

    # Uncomment the admin/doc line below and add 'django.contrib.admindocs' 
    # to INSTALLED_APPS to enable admin documentation:
    # (r'^admin/doc/', include('django.contrib.admindocs.urls')),
    (r'^admin/', include(admin.site.urls)),
    (r'^databrowse/(.*)', databrowse.site.root),
)
