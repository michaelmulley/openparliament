from django.contrib import admin

from parliament.search.models import IndexingTask


class IndexingTaskAdmin(admin.ModelAdmin):

    list_display = ['id', 'action', 'identifier', 'timestamp', 'processed']
    list_filter = ['action', ('processed', admin.EmptyFieldListFilter), 'timestamp']
    search_fields = ['identifier']
    ordering = ['-id']
    readonly_fields = ['processed']


admin.site.register(IndexingTask, IndexingTaskAdmin)
