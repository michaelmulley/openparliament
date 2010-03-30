from django.contrib import admin, databrowse

from parliament.core.models import *

class PoliticianOptions (admin.ModelAdmin):
    
    search_fields = ('name',)
    
class RidingOptions (admin.ModelAdmin):
    list_display = ('name', 'province', 'edid')
    search_fields = ('name',)
    list_filter = ('province',)
    
class SessionOptions (admin.ModelAdmin):
    list_display = ('name', 'start', 'end')
    
class ElectedMemberOptions(admin.ModelAdmin):
    list_display=('politician', 'riding', 'party', 'start_date', 'end_date')
    list_filter=('party',)
    search_fields = ('politician__name',)
    
class InternalXrefOptions(admin.ModelAdmin):
    list_display = ('schema', 'text_value', 'int_value', 'target_id')

admin.site.register(ElectedMember, ElectedMemberOptions)
admin.site.register(Riding, RidingOptions)
admin.site.register(Session, SessionOptions)
admin.site.register(Politician, PoliticianOptions)
admin.site.register(Party)
admin.site.register(InternalXref, InternalXrefOptions)

databrowse.site.register(ElectedMember)
databrowse.site.register(Riding)
databrowse.site.register(Session)
databrowse.site.register(Politician)
databrowse.site.register(Party)
