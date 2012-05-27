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
    'Person': 'politician',
    'MP': 'politician_id',
    'Witness': 'who_hocid',
    'Committee': 'committee_slug',
    'Date': 'date',
    'Type': 'type'
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
            
        query = request.GET['q'].strip()
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
            'rows': PER_PAGE,
            'facet': 'true'
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
                if not match:
                    return ''
                (fromyear, frommonth, toyear, tomonth) = [int(x) for x in match.groups()]
                tomonth += 1
                if tomonth == 13:
                    tomonth = 1
                    toyear += 1
                filter_value = '[{0:02}-{1:02}-01T00:01:01.000Z TO {2:02}-{3:02}-01T00:01:01.000Z]'.format(fromyear, frommonth, toyear, tomonth)

            elif filter_name == 'type':
                filter_name = 'django_ct'
                if filter_value == 'debate':
                    filter_value = 'hansards.statement'
                    filters.append('committee_slug:""')
                elif filter_value == 'committee':
                    filter_value = 'hansards.statement'
                    filters.append('-committee_slug:""')
                elif filter_value == 'bill':
                    filter_value = 'bills.bill'

            if ' ' in filter_value and filter_name != 'date':
                filter_value = u'"%s"' % filter_value

            if filter_name in ['who_hocid', 'politician_id', 'politician']:
                filter_tag = 'fperson'
            else:
                filter_tag = 'f' + filter_name

            filter_types.add(filter_name)
            filters.append(u'{!tag=%s}%s:%s' % (filter_tag, filter_name, filter_value))
            return ''
        bare_query = re.sub(r'(%s): "([^"]+)"' % '|'.join(ALLOWABLE_FILTERS),
            extract_filter, query)
        bare_query = re.sub(r'\s\s+', ' ', bare_query).strip()
        if filters and not bare_query:
            bare_query = '*:*'

        if filters:
            searchparams['fq'] = filters

        committees_only = 'committee_slug' in filter_types or '-committee_slug:""' in filters
        committees_maybe = 'django_ct' not in filter_types or committees_only
        if committees_maybe and not committees_only:
            ctx['discontinuity'] = 2006

        if committees_only:
            searchparams['facet.range.start'] = '2006-01-01T00:00:00.000Z'
        else:
            searchparams['facet.range.start'] = '1994-01-01T00:00:00.000Z'

        for opt in ALLOWABLE_OPTIONS:
            if opt in request.GET and request.GET[opt] in ALLOWABLE_OPTIONS[opt]:
                searchparams[opt] = request.GET[opt] 
                ctx[opt] = request.GET[opt]

        # Our version of pysolr doesn't like Unicode
        if searchparams.get('fq'):
            searchparams['fq'] = map(lambda f: f.encode('utf-8'), searchparams['fq'])
        results = autohighlight(solr.search(bare_query.encode('utf-8'), **searchparams))

        date_counts = []
        if 'facet_ranges' in results.facets:
            datefacets = results.facets['facet_ranges']['date']['counts']
            date_counts = [
                (int(datefacets[i][:4]), datefacets[i+1])
                for i in range(0, len(datefacets), 2)
            ]

        if committees_only:
            # If we're searching only committees, we by definition won't have
            # results before 1994, so let's take them off of the graph.
            date_counts = filter(lambda c: c[0] >= 2006, date_counts)
        ctx.update(
            chart_years = [c[0] for c in date_counts],
            chart_values = [c[1] for c in date_counts],
            facet_fields = results.facets.get('facet_fields'),
            results = results,
            page = SearchPaginator(results, pagenum, PER_PAGE, request.GET)
        )
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