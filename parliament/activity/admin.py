from django.contrib import admin

from parliament.activity.models import *


class ActivityOptions(admin.ModelAdmin):
    list_display = ('politician', 'variety', 'date', 'guid')
    list_filter = ('variety', 'date')
    search_fields = ('politician__name', 'variety')

admin.site.register(Activity, ActivityOptions)
