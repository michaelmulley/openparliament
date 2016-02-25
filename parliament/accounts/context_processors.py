from django.conf import settings

_auth_context = {
    'GOOGLE_CLIENT_ID': getattr(settings, 'GOOGLE_CLIENT_ID', None)
}

def auth(request):
    return _auth_context
