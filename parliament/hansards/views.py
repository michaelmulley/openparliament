from django.template import Context, loader, RequestContext
from django.http import HttpResponse, Http404, HttpResponseRedirect, HttpResponsePermanentRedirect
from django.views import generic

from parliament.hansards.models import Hansard, HansardCache, Statement

def hansard(request, hansard_id):
    hansard = Hansard.objects.get(pk=hansard_id)
    statements = Statement.objects.filter(hansard=hansard).select_related('politician', 'member__riding', 'member__party')
    t = loader.get_template("hansards/hansard_detail.html")
    c = RequestContext(request, {
        'hansard': hansard,
        'statements': statements,
    })
    return HttpResponse(t.render(c))
    
def hansardcache (request, hansard_id):
    cache = HansardCache.objects.get(hansard=hansard_id)
    return HttpResponse(cache.getHTML())
    
def index(request):
    return generic.date_based.archive_index(request, 
        queryset=Hansard.objects.all(), 
        date_field='date',
        extra_context={'title': 'The Debates of the House of Commons'})
        
def by_year(request, year):
    return generic.date_based.archive_year(request,
        queryset=Hansard.objects.all().order_by('date'),
        date_field='date',
        year=year,
        make_object_list=True,
        extra_context={'title': 'Debates from %s' % year})
