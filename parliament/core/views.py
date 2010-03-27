from django.template import Context, loader, RequestContext
from django.http import HttpResponse, Http404, HttpResponseRedirect, HttpResponsePermanentRedirect
from django.db.models import Count
from django.contrib.syndication.views import Feed
from django.shortcuts import get_object_or_404
from django.contrib.markup.templatetags.markup import markdown

from haystack.views import FacetedSearchView
from haystack.forms import FacetedSearchForm, HighlightedSearchForm
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
    
class PoliticianFeed(Feed):
    
    def get_object(self, request, pol_id):
        return get_object_or_404(Politician, pk=pol_id)
    
    def title(self, pol):
        return pol.name
        
    def link(self, pol):
        return "http://openparliament.ca" + pol.get_absolute_url()
        
    def description(self, pol):
        return "Statements by %s in the House of Commons, from openparliament.ca." % pol.name
        
    def items(self, pol):
        return Statement.objects.filter(member__politician=pol).order_by('-time')[:12]
        
    def item_title(self, statement):
        return statement.topic
        
    def item_link(self, statement):
        return statement.get_absolute_url()
        
    def item_description(self, statement):
        return markdown(statement.text)
        
    def item_pubdate(self, statement):
        return statement.time

class ParliamentSearchForm(FacetedSearchForm, HighlightedSearchForm):
    pass
    
tmpsearch = FacetedSearchView(form_class=ParliamentSearchForm, searchqueryset=SearchQuerySet().facet('politician').facet('party').facet('province'))
