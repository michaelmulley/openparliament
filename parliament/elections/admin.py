from django.contrib import admin, databrowse

from parliament.elections.models import *

admin.site.register(Election)
admin.site.register(Candidacy)

databrowse.site.register(Election)
databrowse.site.register(Candidacy)