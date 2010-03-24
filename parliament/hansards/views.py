from django.template import Context, loader, RequestContext
from django.http import HttpResponse, Http404, HttpResponseRedirect, HttpResponsePermanentRedirect

from parliament.hansards.models import Hansard, HansardCache, Statement

def hansard(request, hansard_id):
    hansard = Hansard.objects.get(pk=hansard_id)
    statements = Statement.objects.filter(hansard=hansard).select_related('member__politician', 'member__riding', 'member__party')
    t = loader.get_template("parliament/hansard.html")
    c = RequestContext(request, {
        'hansard': hansard,
        'statements': statements,
    })
    return HttpResponse(t.render(c))
    
def hansardcache (request, hansard_id):
    cache = HansardCache.objects.get(hansard=hansard_id)
    return HttpResponse(cache.getHTML())
