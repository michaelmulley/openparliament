#coding: utf-8

from hashlib import md5
import re
import urllib

from django.conf import settings
from django.contrib.syndication.views import Feed
from django.core.cache import cache
from django.http import HttpResponse, Http404, HttpResponseRedirect, HttpResponsePermanentRedirect
from django.template import Context, loader, RequestContext
from django.utils.safestring import mark_safe
from django.views.decorators.vary import vary_on_headers

import pysolr

from parliament.core import parsetools
from parliament.core.models import Politician, Session, ElectedMember, Riding, InternalXref
from parliament.core.utils import postcode_to_edid
from parliament.core.views import closed, flatpage_response
from parliament.hansards.models import Statement
from parliament.search.utils import autohighlight, SearchPaginator

PER_PAGE = getattr(settings, 'SEARCH_RESULTS_PER_PAGE', 15)
ALLOWABLE_OPTIONS = {
    'sort': ['score desc', 'date asc', 'date desc'],
}

ALLOWABLE_FILTERS = {
    'Party': 'party',
    'Province': 'province',
    'Person': 'politician_id',
    'MP': 'politician_id',
    'Witness': 'who_hocid',
    'Committee': 'committee_slug',
    'Date': 'date'
}
solr = pysolr.Solr(settings.HAYSTACK_SOLR_URL)

@vary_on_headers('X-Requested-With')
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
            'start' : startfrom,
            'rows': PER_PAGE
        }
        ctx = {
            'query': query,
            'pagenum': pagenum,
        }

        # Extract filters from query
        filters = []
        filter_types = set()
        def extract_filter(match):
            filter_name = ALLOWABLE_FILTERS[match.group(1)]
            filter_value = match.group(2)

            if filter_name == 'date':
                match = re.search(r'^(\d{4})-(\d\d?) to (\d{4})-(\d\d?)', filter_value)
                print match
                if not match:
                    return ''
                (fromyear, frommonth, toyear, tomonth) = [int(x) for x in match.groups()]
                tomonth += 1
                if tomonth == 13:
                    tomonth = 1
                    toyear += 1
                filter_value = '[{0:02}-{1:02}-01T00:01:01.000Z TO {2:02}-{3:02}-01T00:01:01.000Z]'.format(fromyear, frommonth, toyear, tomonth)

            filter_types.add(filter_name)
            filters.append(u'%s:%s' % (filter_name, filter_value))
            return ''
        bare_query = re.sub(r'(%s): "([^"]+)"' % '|'.join(ALLOWABLE_FILTERS),
            extract_filter, query)
        bare_query = re.sub(r'\s\s+', ' ', bare_query).strip()
        if filters and not bare_query:
            bare_query = '*:*'

        if filters:
            searchparams['fq'] = filters

        facet_opts = {
            'facet.range': 'date',
            'facet': 'true',
            'facet.range.end': 'NOW',
            'facet.range.gap': '+1YEAR',
        }
        committees_only = 'committee_slug' in filter_types
        if committees_only:
            facet_opts['facet.range.start'] = '2006-01-01T00:00:00.000Z'
        else:
            facet_opts['facet.range.start'] = '1994-01-01T00:00:00.000Z'

        if 'date' not in filter_types:
            searchparams.update(facet_opts)

        for opt in ALLOWABLE_OPTIONS:
            if opt in request.GET and request.GET[opt] in ALLOWABLE_OPTIONS[opt]:
                searchparams[opt] = request.GET[opt] 
                ctx[opt] = request.GET[opt]

        results = autohighlight(solr.search(bare_query, **searchparams))

        if results.facets:
            facet_results = results.facets['facet_ranges']['date']['counts']
        else:
            facet_results = _get_facets(bare_query, searchparams, facet_opts)

        date_counts = [
            (int(facet_results[i][:4]), facet_results[i+1])
            for i in range(0, len(facet_results), 2)
        ]

        if committees_only:
            # If we're searching only committees, we by definition won't have
            # results before 1994, so let's take them off of the graph.
            date_counts = filter(lambda c: c[0] >= 2006, date_counts)

        ctx['chart_years'] = [c[0] for c in date_counts]
        ctx['chart_values'] = [c[1] for c in date_counts]
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

def _get_facets(query, orig_searchparams, facet_opts):
    params = dict(orig_searchparams)
    if params.get('fq'):
        # Remove date filter
        params['fq'] = filter(lambda f: not f.startswith('date:'), params['fq'])

    params.update(facet_opts)

    cache_key = 'facets-' + md5(
        query.encode('utf-8') + repr(params)
    ).hexdigest()
    cache_result = cache.get(cache_key)
    if cache_result:
        return cache_result

    params.update(rows=0)

    result = solr.search(query, **params).facets['facet_ranges']['date']['counts']
    cache.set(cache_key, result, 60 * 60 * 2)
    return result
    
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
                return flatpage_response(request, u"Ain’t nobody lookin’ out for you",
                    mark_safe(u"""It looks like that postal code is in the riding of %s. There is no current
                    Member of Parliament for that riding. By law, a byelection must be called within
                    180 days of a resignation causing a vacancy. (If you think we’ve got our facts
                    wrong about your riding or MP, please send an <a class='maillink'>e-mail</a>.)"""
                    % Riding.objects.get(edid=edid).dashed_name))
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