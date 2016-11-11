from django.contrib import messages
from django.core import urlresolvers
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.http import HttpResponse, HttpResponseRedirect
from django.views.decorators.cache import never_cache

from parliament.accounts.models import LoginToken, TokenError, User
from parliament.core.views import disable_on_readonly_db
from parliament.utils.views import JSONView


class CurrentAccountView(JSONView):

    def get(self, request):
        return {'email': request.authenticated_email}

current_account = never_cache(CurrentAccountView.as_view())

class LogoutView(JSONView):

    def post(self, request):
        request.authenticated_email = None
        return True

logout = never_cache(LogoutView.as_view())

def _get_ip(request):
    ip = request.META['REMOTE_ADDR']
    if ip == '127.0.0.1' and 'HTTP_X_REAL_IP' in request.META:
        ip = request.META['HTTP_X_REAL_IP']
    return ip

class LoginTokenCreateView(JSONView):

    def post(self, request):
        email = request.POST.get('email').lower().strip()
        try:
            EmailValidator()(email)
        except ValidationError as e:
            return HttpResponse(e.message, content_type='text/plain', status=400)
        LoginToken.generate(
            email=email,
            requesting_ip=_get_ip(request)
        )
        return 'sent'

create_token = disable_on_readonly_db(LoginTokenCreateView.as_view())

@never_cache
@disable_on_readonly_db
def token_login(request, token):
    redirect_url = urlresolvers.reverse('alerts_list')

    try:
        lt = LoginToken.validate(token=token, login_ip=_get_ip(request))
    except TokenError as e:
        messages.error(request, e.message)
        return HttpResponseRedirect(redirect_url)

    user, created = User.objects.get_or_create(email=lt.email)
    user.log_in(request)

    if lt.post_login_url:
        redirect_url = lt.post_login_url        
    return HttpResponseRedirect(redirect_url)
