import html
import re

from django import template

register = template.Library()

@register.filter(name='text_highlight')
def text_highlight(s):
    """Plain-text rendering of a highlighted search snippet: **term**."""
    s = re.sub(r'</?em>', '**', html.unescape(str(s)))
    return re.sub(r'\n+', ' ', s)
