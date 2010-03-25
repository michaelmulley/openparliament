from django.template import Context, loader, RequestContext
from django.http import HttpResponse, Http404, HttpResponseRedirect, HttpResponsePermanentRedirect
from django.db.models import Count

from haystack.views import FacetedSearchView
from haystack.forms import FacetedSearchForm, HighlightedModelSearchForm
from haystack.query import SearchQuerySet

from parliament.core.models import Politician
from parliament.hansards.models import Statement

def dupes(request):
    dupelist = Politician.objects.values('name').annotate(namecount=Count('name')).filter(namecount__gt=1).order_by('-namecount')
    dupelist = [Politician.objects.filter(name=i['name']) for i in dupelist]
    t = loader.get_template("parliament/dupes.html")
    c = RequestContext(request, {
        'dupelist': dupelist,
    })
    return HttpResponse(t.render(c))
    
def politician(request, pol_id):
    try:
        pol = Politician.objects.get(pk=pol_id)
    except Politician.DoesNotExist:
        raise Http404
    
    c = RequestContext(request, {
        'pol': pol,
        'candidacies': pol.candidacy_set.all().order_by('-election__date'),
        'statements': Statement.objects.filter(member__politician=pol).order_by('-time')[:10]
    })
    t = loader.get_template("parliament/politician.html")
    return HttpResponse(t.render(c))

class ParliamentSearchForm(FacetedSearchForm, HighlightedModelSearchForm):
    pass
    
tmpsearch = FacetedSearchView(form_class=ParliamentSearchForm, searchqueryset=SearchQuerySet().facet('politician').facet('party').facet('province'))
