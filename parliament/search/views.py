import re
import urllib

from django.template import Context, loader, RequestContext
from django.http import HttpResponse, Http404, HttpResponseRedirect, HttpResponsePermanentRedirect
from django.conf import settings
from django.contrib.syndication.views import Feed
import pysolr

from parliament.core.models import Politician, Session, ElectedMember, Riding, InternalXref
from parliament.hansards.models import Statement
from parliament.core.utils import postcode_to_edid
from parliament.search.utils import autohighlight, SearchPaginator
from parliament.core import parsetools
from parliament.core.views import closed

PER_PAGE = getattr(settings, 'SEARCH_RESULTS_PER_PAGE', 10)
ALLOWABLE_OPTIONS = {
    'sort': ['score desc', 'date asc', 'date desc'],
}
solr = pysolr.Solr(settings.HAYSTACK_SOLR_URL)
def search(request):
    if 'q' in request.GET and request.GET['q']:
        if not 'page' in request.GET:
            resp = try_postcode_first(request)
            if resp: return resp
            resp = try_politician_first(request)
            if resp: return resp
            
        if getattr(settings, 'PARLIAMENT_SEARCH_CLOSED', False):
            return closed(request, message=settings.PARLIAMENT_SEARCH_CLOSED)
            
        query = parsetools.removeAccents(request.GET['q'].strip())        
        if 'page' in request.GET:
            try:
                pagenum = int(request.GET['page'])
            except ValueError:
                pagenum = 1
        else:
            pagenum = 1
        startfrom = (pagenum - 1) * PER_PAGE
        
        searchparams = {
            'start' : startfrom
        }
        ctx = {
            'query': query,
            'pagenum': pagenum
        }
        
        for opt in ALLOWABLE_OPTIONS:
            if opt in request.GET and request.GET[opt] in ALLOWABLE_OPTIONS[opt]:
                searchparams[opt] = request.GET[opt] 
                ctx[opt] = request.GET[opt]
        
        results = autohighlight(solr.search(query, **searchparams))
        ctx['results'] = results
        ctx['page'] = SearchPaginator(results, pagenum, PER_PAGE, request.GET)
    else:
        ctx = {
            'query' : '',
            'page' : None,
        }
    c = RequestContext(request, ctx)
    if request.is_ajax():
        t = loader.get_template("search/search_results.inc")
    else:
        t = loader.get_template("search/search.html")
    return HttpResponse(t.render(c))
    
r_postcode = re.compile(r'^\s*([A-Z][0-9][A-Z])\s*([0-9][A-Z][0-9])\s*$')
def try_postcode_first(request):
    match = r_postcode.search(request.GET['q'].upper())
    if match:
        postcode = match.group(1) + " " + match.group(2)
        try:
            x = InternalXref.objects.filter(schema='edid_postcode', text_value=postcode)[0]
            edid = x.target_id
        except IndexError:
            edid = postcode_to_edid(postcode)
            if edid:
                InternalXref.objects.get_or_create(schema='edid_postcode', text_value=postcode, target_id=edid)
        if edid:
            try:
                member = ElectedMember.objects.get(end_date__isnull=True, riding__edid=edid)
                return HttpResponseRedirect(member.politician.get_absolute_url())
            except ElectedMember.DoesNotExist:
                pass
            except ElectedMember.MultipleObjectsReturned:
                raise Exception("Too many MPs for postcode %s" % postcode)
    return False
    
def try_politician_first(request):
    try:
        pol = Politician.objects.get_by_name(request.GET['q'].strip(), session=Session.objects.current(), saveAlternate=False, strictMatch=True)
        if pol:
            return HttpResponseRedirect(pol.get_absolute_url())
    except:
        return None
        
class SearchFeed(Feed):

    def get_object(self, request):
        if 'q' not in request.GET:
            raise Http404
        return request.GET['q']

    def title(self, query):
        return '"%s" | openparliament.ca' % query

    def link(self, query):
        return "http://openparliament.ca/search/?" + urllib.urlencode({'q': query.encode('utf8'), 'sort': 'date desc'})

    def description(self, query):
        return "From openparliament.ca, search results for '%s'" % query

    def items(self, query):
        return filter(lambda item: item['django_ct'] == 'hansards.statement', 
            autohighlight(solr.search(query, sort='date desc')).docs)

    def item_title(self, item):
        return "%s / %s" % (item['topic'], item['politician'])

    def item_link(self, item):
        return item['url']

    def item_description(self, item):
        return item['text']

    def item_pubdate(self, item):
        return item['date']