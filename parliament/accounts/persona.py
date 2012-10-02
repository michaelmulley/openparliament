import browserid

from django.conf import settings

from parliament.accounts.models import User
from parliament.utils.views import JSONView

def get_user_from_persona_assertion(assertion, audience=settings.SITE_URL):
    data = browserid.verify(assertion, audience)
    assert data['email']
    user, created = User.objects.get_or_create(email=data['email'].lower().strip())
    return user

class PersonaLoginEndpointView(JSONView):

    def post(self, request):
        user = get_user_from_persona_assertion(request.POST.get('assertion'))
        user.log_in(request)
        return {'email': user.email}

class PersonaLogoutEndpointView(JSONView):

    def post(self, request):
        request.session['authenticated_email'] = None
        return True
