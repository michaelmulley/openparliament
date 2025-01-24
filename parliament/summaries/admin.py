from django.contrib import admin

from parliament.summaries.models import *

class SummaryAdmin(admin.ModelAdmin):
    list_display = ('summary_type', 'identifier', 'created', 'public')
    list_filter = ('summary_type', 'public')
    search_fields = ('identifier',)

class SummaryPollAdmin(admin.ModelAdmin):
    list_display = ('summary', 'vote', 'created', 'user_ip')
    list_filter = ('vote',)

admin.site.register(Summary, SummaryAdmin)
admin.site.register(SummaryPoll, SummaryPollAdmin)