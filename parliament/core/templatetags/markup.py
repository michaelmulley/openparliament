from django import template
from django.conf import settings
from django.utils.encoding import force_str
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter(is_safe=True)
def markdown(value):
    try:
        import markdown
    except ImportError:
        if settings.DEBUG:
            raise template.TemplateSyntaxError("Error in 'markdown' filter: The Python markdown library isn't installed.")
        return force_str(value)
    return mark_safe(markdown.markdown(force_str(value)))
