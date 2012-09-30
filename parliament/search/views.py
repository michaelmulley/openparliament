#coding: utf-8

import re
import urllib

from django.conf import settings
from django.contrib.syndication.views import Feed
from django.http import HttpResponse, Http404, HttpResponseRedirect, HttpResponsePermanentRedirect
from django.template import loader, RequestContext
from django.utils.safestring import mark_safe
from django.views.decorators.vary import vary_on_headers

from parliament.core.models import Politician, Session, ElectedMember, Riding, InternalXref
from parliament.core.utils import postcode_to_edid
from parliament.core.views import closed, flatpage_response
from parliament.search.solr import SearchQuery
from parliament.search.utils import SearchPaginator

PER_PAGE = getattr(settings, 'SEARCH_RESULTS_PER_PAGE', 15)


@vary_on_headers('X-Requested-With')
def search(request):
    if getattr(settings, 'PARLIAMENT_SEARCH_CLOSED', False):
        return closed(request, message=settings.PARLIAMENT_SEARCH_CLOSED)

    if 'q' in request.GET and request.GET['q']:
        if not 'page' in request.GET:
            resp = try_postcode_first(request)
            if resp: return resp
            resp = try_politician_first(request)
            if resp: return resp

        query = request.GET['q'].strip()
        if request.GET.get('prepend'):
            query = request.GET['prepend'] + u' ' + query
        if 'page' in request.GET:
            try:
                pagenum = int(request.GET['page'])
            except ValueError:
                pagenum = 1
        else:
            pagenum = 1
        startfrom = (pagenum - 1) * PER_PAGE

        query_obj = SearchQuery(query,
            start=startfrom,
            limit=PER_PAGE,
            user_params=request.GET,
            facet=True)

        ctx = dict(
            query=query,
            pagenum=pagenum,
            discontinuity=query_obj.discontinuity,
            chart_years=[c[0] for c in query_obj.date_counts],
            chart_values=[c[1] for c in query_obj.date_counts],
            facet_fields=query_obj.facet_fields,
            page=SearchPaginator(query_obj.documents, query_obj.hits,
                pagenum, PER_PAGE, request.GET)
        )

        ctx.update(query_obj.validated_user_params)

    else:
        ctx = {
            'query': '',
            'page': None,
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
        query_obj = SearchQuery(query, user_params={'sort': 'date desc'})
        return filter(lambda item: item['django_ct'] == 'hansards.statement',
            query_obj.documents)

    def item_title(self, item):
        return "%s / %s" % (item['topic'], item['politician'])

    def item_link(self, item):
        return item['url']

    def item_description(self, item):
        return item['text']

    def item_pubdate(self, item):
        return item['date']
