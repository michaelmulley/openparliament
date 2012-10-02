from django.contrib import admin

from parliament.alerts.models import *

class PoliticianAlertAdmin(admin.ModelAdmin):
    
    list_display = ('email', 'politician', 'active', 'created')
    search_fields = ('email', 'politician__name')
    
admin.site.register(PoliticianAlert, PoliticianAlertAdmin)

admin.site.register(Topic)
admin.site.register(Subscription)
admin.site.register(SeenItem)