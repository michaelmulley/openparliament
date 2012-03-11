from django.contrib import admin

from parliament.elections.models import *

admin.site.register(Election)
admin.site.register(Candidacy)