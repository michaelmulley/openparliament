import datetime, re

from django import template
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe

from parliament.core.models import PROVINCE_LOOKUP

register = template.Library()

@register.filter(name='expand_province')
def expand_province(value):
    return PROVINCE_LOOKUP.get(value, None)
    
@register.filter(name='heshe')
def heshe(pol):
    if pol.gender == 'F':
        return 'She'
    elif pol.gender =='M':
        return 'He'
    else:
        return 'He/she'
        
@register.filter(name='hisher')
def heshe(pol):
    if pol.gender == 'F':
        return 'Her'
    elif pol.gender == 'M':
        return 'His'
    else:
        return 'Their'
        
@register.filter(name='himher')
def himher(pol):
    if pol.gender == 'F':
        return 'Her'
    elif pol.gender == 'M':
        return 'Him'
    else:
        return 'Them'
        
@register.filter(name='mrms')
def mrms(pol):
    if pol.gender == 'M':
        return 'Mr.'
    elif pol.gender == 'F':
        return 'Ms.'
    else:
        return 'Mr./Ms.'
        
@register.filter(name='month_num')
def month_num(month):
    return datetime.date(2010, month, 1).strftime("%B")
    
@register.filter(name='strip_act')
def strip_act(value):
    value = re.sub(r'An Act (to )?([a-z])', lambda m: m.group(2).upper(), value)
    return re.sub(r' Act$', '', value)
    
@register.filter(name='time_since')
def time_since(value):
    today = datetime.date.today()
    days_since = (today - value).days
    if value > today or days_since == 0:
        return 'Today'
    elif days_since == 1:
        return 'Yesterday'
    elif days_since == 2:
        return 'Two days ago'
    elif days_since == 3:
        return 'Three days ago'
    elif days_since < 7:
        return 'This week'
    elif days_since < 14:
        return 'A week ago'
    elif days_since < 21:
        return 'Two weeks ago'
    elif days_since < 28:
        return 'Three weeks ago'
    elif days_since < 45:
        return 'A month ago'
    elif days_since < 75:
        return 'Two months ago'
    elif days_since < 105:
        return 'Three months ago'
    else:
        return 'More than three months ago'
        
@register.filter(name='english_list')
def english_list(value, arg=', '):
    if not type(value) == list:
        raise Exception("Tag english_list takes a list as argument")
    if len(value) == 1:
        return "%s" % value[0]
    elif len(value) == 0:
        return ''
    elif len(value) == 2:
        return "%s and %s" % (value[0], value[1])
    else:
        return "%s%s and %s" % (arg.join(value[0:-1]), arg, value[-1])
        
@register.filter(name='list_prefix')
def list_prefix(value, arg):
    return ["%s%s" % (arg, i) for i in value]
    
@register.filter(name='list_filter')
def list_filter(value, arg):
    return [x for x in value if x != arg]

@register.filter(name='round')
def roundfilter(value, arg):
    return round(value, int(arg))

@register.filter(name='friendly_minutes')
def friendly_minutes(mins):
    if mins <= 45:
        return f'{mins} minutes'
    hours = round(mins / 60)
    return "1 hour" if hours == 1 else f"{hours} hours"

@register.filter(name="markdown_links")
def markdown_links(text):
    """
    Process Markdown, but only links and bold to prevent unexpected results.
    """
    text = conditional_escape(text)
    text = re.sub(r'\[(.*?)\]\((/.*?)\)', r'<a href="\2">\1</a>', text)
    # Also convert Markdown bolded text
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    return mark_safe(text)