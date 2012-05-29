from django.contrib import admin

from parliament.search.models import *

class IndexingTaskAdmin(admin.ModelAdmin):

    list_display = ['action', 'identifier', 'timestamp', ] #'content_object']
    list_filter = ['action', 'timestamp']

admin.site.register(IndexingTask, IndexingTaskAdmin)