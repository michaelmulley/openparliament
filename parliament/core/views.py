from django.template import Context, loader, RequestContext
from django.http import HttpResponse, Http404, HttpResponseRedirect, HttpResponsePermanentRedirect

from parliament.hansards.models import Hansard
from parliament.core.models import SiteNews

def home(request):
    
    t = loader.get_template("home.html")
    c = RequestContext(request, {
        'latest_hansard': Hansard.objects.all()[0],
        'sitenews': SiteNews.objects.filter(active=True)[:6],
    })
    return HttpResponse(t.render(c))