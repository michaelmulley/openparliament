from django.views.decorators.cache import never_cache

from parliament.core.api import JSONView


class CurrentAccountView(JSONView):

    def get(self, request):
        return {'email': request.authenticated_email}

current_account = never_cache(CurrentAccountView.as_view())