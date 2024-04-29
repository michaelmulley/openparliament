
from json import dumps

from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter(name='json')
def jsonfilter(obj):
    return mark_safe(
        dumps(obj)
    )
