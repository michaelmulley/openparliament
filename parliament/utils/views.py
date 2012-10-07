from django.http import HttpResponse, HttpResponseRedirect


class AjaxRedirectResponse(HttpResponse):

    def __init__(self, url, status_code=403):
        super(AjaxRedirectResponse, self).__init__(
            '<script>window.location.href = "%s";</script>' % url,
            content_type='text/html'
        )
        self.status_code = status_code
        self['X-OP-Redirect'] = url


def adaptive_redirect(request, url):
    if request.is_ajax():
        return AjaxRedirectResponse(url)
    return HttpResponseRedirect(url)
