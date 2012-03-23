from django.contrib import admin

from parliament.core.models import *


class PoliticianInfoInline(admin.TabularInline):
    model = PoliticianInfo


class PoliticianOptions (admin.ModelAdmin):
    inlines = [PoliticianInfoInline]
    search_fields = ('name',)


class RidingOptions (admin.ModelAdmin):
    list_display = ('name', 'province', 'edid')
    search_fields = ('name',)
    list_filter = ('province',)


class SessionOptions (admin.ModelAdmin):
    list_display = ('name', 'start', 'end')


class ElectedMemberOptions(admin.ModelAdmin):
    list_display = (
        'politician',
        'riding',
        'party',
        'start_date',
        'end_date'
    )
    list_filter = ('party',)
    search_fields = ('politician__name',)


class InternalXrefOptions(admin.ModelAdmin):
    list_display = ('schema', 'text_value', 'int_value', 'target_id')
    search_fields = ('schema', 'text_value', 'int_value', 'target_id')
    list_editable = ('text_value', 'int_value', 'target_id')


class PartyOptions(admin.ModelAdmin):
    list_display = ('name', 'short_name', 'slug')


class PoliticianInfoOptions(admin.ModelAdmin):
    list_display = ('politician', 'schema', 'value')
    search_fields = ('politician__name', 'schema', 'value')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "politician":
            kwargs["queryset"] = Politician.objects.elected()
            return db_field.formfield(**kwargs)
        return super(MyModelAdmin, self).formfield_for_foreignkey(
            db_field,
            request,
            **kwargs
        )


class SiteNewsOptions(admin.ModelAdmin):
    list_display = ('title', 'date', 'active')


admin.site.register(ElectedMember, ElectedMemberOptions)
admin.site.register(Riding, RidingOptions)
admin.site.register(Session, SessionOptions)
admin.site.register(Politician, PoliticianOptions)
admin.site.register(Party, PartyOptions)
admin.site.register(InternalXref, InternalXrefOptions)
admin.site.register(PoliticianInfo, PoliticianInfoOptions)
admin.site.register(SiteNews, SiteNewsOptions)

