import re

from django.template import Context, loader, RequestContext
from django.http import HttpResponse, Http404, HttpResponseRedirect, HttpResponsePermanentRedirect
from django.conf import settings
import pysolr

from parliament.core.models import Politician, Session, ElectedMember, Riding, InternalXref
from parliament.hansards.models import Statement
from parliament.core.utils import postcode_to_edid
from parliament.search.utils import autohighlight, SearchPaginator
from parliament.core import parsetools

def search(request):
    PER_PAGE = getattr(settings, 'SEARCH_RESULTS_PER_PAGE', 10)
    if 'q' in request.GET:
        if not 'page' in request.GET:
            resp = try_postcode_first(request)
            if resp: return resp
            
        query = parsetools.removeAccents(request.GET['q'].strip())
        solr = pysolr.Solr(settings.HAYSTACK_SOLR_URL)
        
        if 'page' in request.GET:
            try:
                pagenum = int(request.GET['page'])
            except ValueError:
                pagenum = 1
        else:
            pagenum = 1
        startfrom = (pagenum - 1) * PER_PAGE
        results = autohighlight(solr.search(query, start=startfrom))
        ctx = {
            'query': query,
            'results': results,
            'pagenum': pagenum,
            'page': SearchPaginator(results, pagenum, PER_PAGE, request.GET, ['q']),
        }
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
            x = InternalXref.objects.get(schema='edid_postcode', text_value=postcode)
            edid = x.target_id
        except InternalXref.DoesNotExist:
            edid = postcode_to_edid(postcode)
            if edid:
                InternalXref(schema='edid_postcode', text_value=postcode, target_id=edid).save()
        if edid:
            try:
                member = ElectedMember.objects.get(end_date__isnull=True, riding__edid=edid)
                return HttpResponseRedirect(member.politician.get_absolute_url())
            except ElectedMember.DoesNotExist:
                pass
            except ElectedMember.MultipleObjectsReturned:
                raise Exception("Too many MPs for postcode %s" % postcode)
    return False