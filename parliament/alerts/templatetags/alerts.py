import html
import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

# Styles for the HTML e-mails. They're inline because some clients drop <style>.
HIGHLIGHT_STYLE = 'background-color:#fff3b0;color:#222222;font-weight:bold;'
PARAGRAPH_STYLE = 'margin:0 0 12px 0;'


@register.filter(name='text_highlight')
def text_highlight(s):
    """Plain-text rendering of a highlighted search snippet: **term**."""
    s = re.sub(r'</?em>', '**', html.unescape(str(s)))
    return re.sub(r'\n+', ' ', s)


@register.filter(name='html_highlight')
def html_highlight(s):
    """E-mail HTML for a highlighted search snippet. The snippet is already
    HTML-escaped by Elasticsearch apart from its <em> tags."""
    s = re.sub(r'<em>', '<strong style="%s">' % HIGHLIGHT_STYLE, str(s))
    s = s.replace('</em>', '</strong>')
    return mark_safe(re.sub(r'\n+', ' ', s))


@register.filter(name='email_paragraphs')
def email_paragraphs(s):
    """E-mail HTML for plain text: a styled <p> per blank-line-separated paragraph."""
    paras = [p.strip() for p in re.split(r'\n\s*\n', str(s)) if p.strip()]
    return mark_safe(''.join(
        '<p style="%s">%s</p>' % (PARAGRAPH_STYLE, escape(p).replace('\n', '<br>'))
        for p in paras))
