from django.contrib import admin

from parliament.alerts.models import *

class TopicAdmin(admin.ModelAdmin):

    list_display = ['query', 'created', 'last_found']
    search_fields = ['query']
    ordering = ['-created']


class SubscriptionAdmin(admin.ModelAdmin):

    list_display = ['user', 'topic', 'active', 'created', 'last_sent']
    search_fields = ['user__email']
    list_filter = ['active', 'created', 'last_sent']
    ordering = ['-created']

admin.site.register(Topic, TopicAdmin)
admin.site.register(Subscription, SubscriptionAdmin)


class TopicMatchAdmin(admin.ModelAdmin):

    list_display = ['topic', 'item_id', 'date', 'created', 'sent']
    list_filter = ['sent', 'created']
    search_fields = ['topic__query', 'item_id']
    ordering = ['-created']

admin.site.register(TopicMatch, TopicMatchAdmin)