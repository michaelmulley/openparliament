import datetime, re

from django import template

from parliament.core.models import PROVINCE_LOOKUP

register = template.Library()

@register.filter(name='expand_province')
def expand_province(value):
    return PROVINCE_LOOKUP[value]
    
@register.filter(name='heshe')
def heshe(pol):
    if pol.gender == 'F':
        return 'She'
    elif pol.gender =='M':
        return 'He'
    else:
        return 'They'
        
@register.filter(name='hisher')
def heshe(pol):
    if pol.gender == 'F':
        return 'Her'
    elif pol.gender == 'M':
        return 'His'
    else:
        return 'Their'
        
@register.filter(name='month_num')
def month_num(month):
    return datetime.date(2010, month, 1).strftime("%B")
    
@register.filter(name='strip_act')
def strip_act(value):
    return re.sub(r'An Act (to )?([a-z])', lambda m: m.group(2).upper(), value)