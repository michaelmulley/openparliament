from django import template
from django.core.serializers.json import simplejson as json
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter(name='json')
def jsonfilter(obj):
    return mark_safe(
        json.dumps(obj)
    )
