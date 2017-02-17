from django.conf import settings
from django.template import loader

def server_error(request, template_name='500.html'):
    "Always includes MEDIA_URL"
    from django.http import HttpResponseServerError
    t = loader.get_template(template_name)
    return HttpResponseServerError(t.render({
        'MEDIA_URL': settings.MEDIA_URL,
        'STATIC_URL': settings.STATIC_URL
    }))
