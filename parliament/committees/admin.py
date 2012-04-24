from django.contrib import admin

from parliament.committees.models import *


class CommitteeAdmin(admin.ModelAdmin):
    list_display = ('short_name', 'slug', 'latest_session')
    list_filter = ('sessions',)


class CommitteeInSessionAdmin(admin.ModelAdmin):
    list_display = ('committee', 'acronym', 'session')


class MeetingAdmin(admin.ModelAdmin):
    list_display = (
        'committee',
        'number',
        'date',
        'start_time',
        'end_time',
        'notice',
        'minutes',
        'evidence',
        'in_camera'
    )
    list_filter = ('committee', 'date')


class ReportAdmin(admin.ModelAdmin):
    list_display = (
        'committee',
        'number',
        'session',
        'name',
        'government_response'
    )
    list_filter = ('committee', 'session', 'government_response')


class ActivityAdmin(admin.ModelAdmin):
    list_display = ('name_en', 'committee', 'study')
    list_filter = ('committee', 'study')


admin.site.register(Committee, CommitteeAdmin)
admin.site.register(CommitteeInSession, CommitteeInSessionAdmin)
admin.site.register(CommitteeMeeting, MeetingAdmin)
admin.site.register(CommitteeReport, ReportAdmin)
admin.site.register(CommitteeActivity, ActivityAdmin)
