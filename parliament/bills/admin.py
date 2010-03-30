from django.contrib import admin

from parliament.bills.models import *

class BillOptions(admin.ModelAdmin):
    raw_id_fields = ('sponsor_member','sponsor_politician')
    list_display = ('number', 'name', 'session', 'privatemember', 'sponsor_politician')

admin.site.register(Bill, BillOptions)