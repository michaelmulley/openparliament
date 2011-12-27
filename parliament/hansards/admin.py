from django.contrib import admin, databrowse

from parliament.hansards.models import *

class DocumentOptions(admin.ModelAdmin):
    list_display=('number', 'date', 'session', 'document_type', 'committeemeeting')
    list_filter=('document_type', 'session', 'date', 'multilingual', 'public')
    
admin.site.register(Document, DocumentOptions)
admin.site.register(Statement)

databrowse.site.register(Statement)
databrowse.site.register(Document)