from django.contrib import admin

from parliament.committees.models import *

class CommitteeAdmin(admin.ModelAdmin):
    list_display = ('short_name', 'slug', 'latest_session', 'display')
    list_filter = ('sessions', 'display')

class CommitteeInSessionAdmin(admin.ModelAdmin):
    list_display = ('committee', 'acronym', 'session')

class MeetingAdmin(admin.ModelAdmin):
    list_display = ('committee', 'number', 'date', 'start_time', 'end_time', 'notice', 'minutes', 'evidence',
        'in_camera')
    list_filter = ('committee', 'date')
    raw_id_fields = ('evidence', 'activities')
    search_fields = ['number', 'committee__name_en', 'source_id']
    
class ReportAdmin(admin.ModelAdmin):
    list_display = ('committee', 'number', 'session', 'name', 'government_response')
    list_filter = ('committee', 'session', 'government_response')
    search_fields = ('name_en', 'number')
    
class ActivityAdmin(admin.ModelAdmin):
    list_display = ('name_en', 'committee', 'study')
    list_filter = ('committee', 'study')
    search_fields = ('name_en',)

admin.site.register(Committee, CommitteeAdmin)
admin.site.register(CommitteeInSession, CommitteeInSessionAdmin)
admin.site.register(CommitteeMeeting, MeetingAdmin)
admin.site.register(CommitteeReport, ReportAdmin)
admin.site.register(CommitteeActivity, ActivityAdmin)
