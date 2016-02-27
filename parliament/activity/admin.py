from django.contrib import admin

from parliament.activity.models import Activity

class ActivityOptions(admin.ModelAdmin):
    list_display = ('politician', 'variety', 'date', 'active', 'guid')
    list_filter = ('variety', 'date', 'active')
    search_fields = ('politician__name', 'variety')

admin.site.register(Activity, ActivityOptions)
