from django import template

from parliament.core.models import PROVINCE_LOOKUP

register = template.Library()

@register.filter(name='expand_province')
def expand_province(value):
    return PROVINCE_LOOKUP[value]