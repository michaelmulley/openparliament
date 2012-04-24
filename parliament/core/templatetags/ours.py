import datetime
import re
import types

from django import template
from django.utils.translation import ugettext as _

from parliament.core.models import PROVINCE_LOOKUP

register = template.Library()


@register.filter(name='expand_province')
def expand_province(value):
    return PROVINCE_LOOKUP.get(value, None)


@register.filter(name='heshe')
def heshe(pol):
    if pol.gender == 'F':
        return _('She')
    elif pol.gender == 'M':
        return _('He')
    else:
        return _('He/she')


@register.filter(name='hisher')
def heshe(pol):
    if pol.gender == 'F':
        return _('Her')
    elif pol.gender == 'M':
        return _('His')
    else:
        return _('Their')


@register.filter(name='himher')
def himher(pol):
    if pol.gender == 'F':
        return _('Her')
    elif pol.gender == 'M':
        return _('Him')
    else:
        return _('Them')


@register.filter(name='mrms')
def mrms(pol):
    if pol.gender == 'M':
        return _('Mr.')
    elif pol.gender == 'F':
        return _('Ms.')
    else:
        return _('Mr./Ms.')


@register.filter(name='month_num')
def month_num(month):
    return datetime.date(2010, month, 1).strftime("%B")


@register.filter(name='strip_act')
def strip_act(value):
    return re.sub(r'An Act (to )?([a-z])', lambda m: m.group(2).upper(), value)


@register.filter(name='time_since')
def time_since(value):
    today = datetime.date.today()
    days_since = (today - value).days
    if value > today or days_since == 0:
        return _('Today')
    elif days_since == 1:
        return _('Yesterday')
    elif days_since == 2:
        return _('Two days ago')
    elif days_since == 3:
        return _('Three days ago')
    elif days_since < 7:
        return _('This week')
    elif days_since < 14:
        return _('A week ago')
    elif days_since < 21:
        return _('Two weeks ago')
    elif days_since < 28:
        return _('Three weeks ago')
    elif days_since < 45:
        return _('A month ago')
    elif days_since < 75:
        return _('Two months ago')
    elif days_since < 105:
        return _('Three months ago')
    else:
        return _('More than three months ago')


@register.filter(name='english_list')
def english_list(value, arg=', '):
    if not type(value) == types.ListType:
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
    return filter(lambda x: x != arg, value)
