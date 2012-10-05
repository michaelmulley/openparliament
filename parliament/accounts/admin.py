from django.contrib import admin

from parliament.accounts.models import *

class UserAdmin(admin.ModelAdmin):

    list_display = ['email', 'created', 'last_login', 'email_bouncing']
    search_fields = ['email']
    list_filter = ['last_login', 'created', 'email_bouncing']

admin.site.register(User, UserAdmin)