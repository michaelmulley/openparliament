from django.contrib import admin

from .models import Haiku

class HaikuAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'pk', 'worthy')
    list_editable = ['worthy']

admin.site.register(Haiku, HaikuAdmin)
