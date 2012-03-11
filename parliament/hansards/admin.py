from django.contrib import admin

from parliament.hansards.models import *

class DocumentOptions(admin.ModelAdmin):
    list_display=('number', 'date', 'session', 'document_type', 'committeemeeting')
    list_filter=('document_type', 'session', 'date', 'multilingual', 'public')
    
admin.site.register(Document, DocumentOptions)
admin.site.register(Statement)