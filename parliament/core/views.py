from django.template import Context, loader, RequestContext
from django.http import HttpResponse, Http404, HttpResponseRedirect, HttpResponsePermanentRedirect
from django.db.models import Count

from haystack.views import FacetedSearchView
from haystack.forms import FacetedSearchForm, HighlightedModelSearchForm
from haystack.query import SearchQuerySet

from parliament.core.models import Politician

def dupes(request):
    dupelist = Politician.objects.values('name').annotate(namecount=Count('name')).filter(namecount__gt=1).order_by('-namecount')
    dupelist = [Politician.objects.filter(name=i['name']) for i in dupelist]
    t = loader.get_template("parliament/dupes.html")
    c = RequestContext(request, {
        'dupelist': dupelist,
    })
    return HttpResponse(t.render(c))
    
    
class ParliamentSearchForm(FacetedSearchForm, HighlightedModelSearchForm):
    pass
    
tmpsearch = FacetedSearchView(form_class=ParliamentSearchForm, searchqueryset=SearchQuerySet().facet('politician').facet('party').facet('province'))
