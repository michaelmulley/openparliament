from django.contrib import admin

from parliament.alerts.models import *

class PoliticianAlertAdmin(admin.ModelAdmin):
    
    list_display = ('email', 'politician', 'active', 'created')
    
admin.site.register(PoliticianAlert, PoliticianAlertAdmin)