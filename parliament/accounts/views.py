from django.contrib import messages
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseNotAllowed
from django.views.decorators.cache import never_cache

from parliament.accounts.models import LoginToken, TokenError, User
from parliament.core.views import disable_on_readonly_db
from parliament.core.utils import get_client_ip
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

class LoginTokenCreateView(JSONView):

    def post(self, request):
        email = request.POST.get('email').lower().strip()
        try:
            EmailValidator()(email)
        except ValidationError as e:
            return HttpResponse(e.message, content_type='text/plain', status=400)
        LoginToken.generate(
            email=email,
            requesting_ip=get_client_ip(request)
        )
        return 'sent'

create_token = disable_on_readonly_db(LoginTokenCreateView.as_view())

@never_cache
@disable_on_readonly_db
def token_login(request, token):
    if request.method != 'GET':
        # Some email systems make HEAD requests to all URLs
        return HttpResponseNotAllowed(['GET'])

    redirect_url = reverse('alerts_list')

    try:
        lt = LoginToken.validate(token=token, login_ip=get_client_ip(request))
    except TokenError as e:
        messages.error(request, str(e))
        return HttpResponseRedirect(redirect_url)

    user, created = User.objects.get_or_create(email=lt.email)
    user.log_in(request)

    if lt.post_login_url:
        redirect_url = lt.post_login_url        
    return HttpResponseRedirect(redirect_url)
