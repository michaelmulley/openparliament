import re

from django import template

register = template.Library()

@register.filter(name='text_highlight')
def text_highlight(s):
    s = re.sub(r'</?em>', '**', s.replace('&gt;', '>').replace('&lt;', '<').replace('&quot;', '"').replace('&amp;', '&'))
    s = re.sub(r'\n+', ' ', s)
    return re.sub('&#(\d+);', lambda m: chr(int(m.group(1))), s)

