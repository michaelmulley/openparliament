from django.contrib import admin

from parliament.summaries.models import *

@admin.display(description='Summary Type')
def raw_summary_type(obj):
    return obj.summary_type
class SummaryAdmin(admin.ModelAdmin):
    list_display = (raw_summary_type, 'identifier', 'created', 'public') #, 'total_tokens')
    list_filter = ('summary_type', 'public')
    search_fields = ('identifier',)

class SummaryPollAdmin(admin.ModelAdmin):
    list_display = ('summary', 'vote', 'created', 'user_ip')
    list_filter = ('vote',)

admin.site.register(Summary, SummaryAdmin)
admin.site.register(SummaryPoll, SummaryPollAdmin)