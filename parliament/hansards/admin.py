from django.contrib import admin, databrowse

from parliament.hansards.models import *

class HansardOptions(admin.ModelAdmin):
    list_display=('number', 'date', 'session')
    
admin.site.register(Hansard, HansardOptions)
admin.site.register(Statement)

databrowse.site.register(Statement)
databrowse.site.register(Hansard)