from django.conf import settings
from django.http import HttpRequest

EMAIL_COOKIE_NAME = 'email'


class AuthenticatedEmailDescriptor(object):
    """Make request.authenticated_email an alias of request.session['_ae']"""

    def __get__(self, request, objtype=None):
        return request.session.get('_ae')

    def __set__(self, request, email):
        request.session['_ae'] = email
        request.session.modified = True


class AuthenticatedEmailUserDescriptor(object):

    def __get__(self, request, objtype=None):
        from parliament.accounts.models import User
        if not request.authenticated_email:
            return None
        try:
            user = User.objects.get(
                email=request.authenticated_email)
        except User.DoesNotExist:
            user = None
        request.authenticated_email_user = user
        return user

HttpRequest.authenticated_email = AuthenticatedEmailDescriptor()
HttpRequest.authenticated_email_user = AuthenticatedEmailUserDescriptor()


class AuthenticatedEmailMiddleware:
    """Keep a JS-readable cookie with the user's email, and ensure it's
    synchronized with the session."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        assert not hasattr(request, 'session'), "AuthenticatedEmailMiddleware must be before SessionMiddleware"
        response = self.get_response(request)

        if settings.SESSION_COOKIE_NAME in response.cookies:
            # We're setting the session cookie, so update the email cookie
            if request.authenticated_email:
                response.cookies[EMAIL_COOKIE_NAME] = request.authenticated_email
                response.cookies[EMAIL_COOKIE_NAME].update(
                    response.cookies[settings.SESSION_COOKIE_NAME].copy())
                response.cookies[EMAIL_COOKIE_NAME]['httponly'] = ''
            else:
                response.delete_cookie(EMAIL_COOKIE_NAME)

        return response
