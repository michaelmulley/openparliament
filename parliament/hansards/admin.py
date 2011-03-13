from django.contrib import admin, databrowse

from parliament.hansards.models import *

class DocumentOptions(admin.ModelAdmin):
    list_display=('number', 'date', 'session')
    list_filter=('session', 'date')
    
admin.site.register(Document, DocumentOptions)
admin.site.register(Statement)

databrowse.site.register(Statement)
databrowse.site.register(Document)