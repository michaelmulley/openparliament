import re

from django.template import Context, loader, RequestContext
from django.http import HttpResponse, Http404, HttpResponseRedirect, HttpResponsePermanentRedirect
from django.db.models import Count
from django.shortcuts import get_object_or_404

from haystack.views import FacetedSearchView, SearchView
from haystack.forms import FacetedSearchForm, HighlightedSearchForm
from haystack.query import SearchQuerySet

from parliament.core.models import Politician, Session, ElectedMember, Riding
from parliament.hansards.models import Statement
from parliament.core.utils import postcode_to_edid

def dupes(request):
    dupelist = Politician.objects.values('name').annotate(namecount=Count('name')).filter(namecount__gt=1).order_by('-namecount')
    dupelist = [Politician.objects.filter(name=i['name']) for i in dupelist]
    t = loader.get_template("parliament/dupes.html")
    c = RequestContext(request, {
        'dupelist': dupelist,
    })
    return HttpResponse(t.render(c))

class ParliamentSearchForm(HighlightedSearchForm): # FacetedSearchForm
    pass

haystackview = SearchView(form_class=ParliamentSearchForm)

r_postcode = re.compile(r'^\s*([A-Z][0-9][A-Z])\s*([0-9][A-Z][0-9])\s*$')
def search(request):
    if 'q' in request.GET:
        match = r_postcode.search(request.GET['q'].upper())
        if match:
            postcode = match.group(1) + " " + match.group(2)
            edid = postcode_to_edid(postcode)
            if edid:
                try:
                    member = ElectedMember.objects.get(session=Session.objects.current(), riding__edid=edid)
                    return HttpResponseRedirect(member.politician.get_absolute_url())
                except ElectedMember.DoesNotExist:
                    pass
                except ElectedMember.MultipleObjectsReturned:
                    raise Exception("Too many MPs for postcode %s" % postcode)
    return haystackview(request)
#tmpsearch = FacetedSearchView(form_class=ParliamentSearchForm, searchqueryset=SearchQuerySet().facet('politician').facet('party').facet('province'))
