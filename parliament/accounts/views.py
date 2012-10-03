from django.views.decorators.cache import never_cache

from parliament.utils.views import JSONView


class CurrentAccountView(JSONView):

    def get(self, request):
        return request.authenticated_email

current_account = never_cache(CurrentAccountView.as_view())