# coding: utf-8

import logging
import re
import urllib.request, urllib.parse, urllib.error
from urllib.parse import urljoin

from django.conf import settings
from django.contrib.syndication.views import Feed
from django.http import HttpResponse, Http404, HttpResponseRedirect, HttpResponsePermanentRedirect
from django.template import loader
from django.utils.safestring import mark_safe
from django.views.decorators.vary import vary_on_headers

import requests

from parliament.core.models import Politician, Session, ElectedMember, Riding, RidingPostcodeCache
from parliament.core.views import closed, flatpage_response
from parliament.core.utils import is_ajax
from parliament.search.solr import SearchQuery
from parliament.search.utils import SearchPaginator
from parliament.utils.views import adaptive_redirect

logger = logging.getLogger(__name__)

PER_PAGE = getattr(settings, 'SEARCH_RESULTS_PER_PAGE', 15)


@vary_on_headers('X-Requested-With')
def search(request):
    if getattr(settings, 'PARLIAMENT_SEARCH_CLOSED', False):
        return closed(request, message=settings.PARLIAMENT_SEARCH_CLOSED)

    if 'q' in request.GET and request.GET['q']:
        if not 'page' in request.GET:
            resp = try_postcode_first(request)
            if resp: return resp
            if not is_ajax(request):
                resp = try_politician_first(request)
                if resp: return resp

        query = request.GET['q'].strip()
        if request.GET.get('prepend'):
            query = request.GET['prepend'] + ' ' + query
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
                pagenum, PER_PAGE)
        )

        ctx.update(query_obj.validated_user_params)

    else:
        ctx = {
            'query': '',
            'page': None,
        }
    if is_ajax(request):
        t = loader.get_template("search/search_results.inc")
    else:
        t = loader.get_template("search/search.html")
    return HttpResponse(t.render(ctx, request))


r_postcode = re.compile(r'^\s*([A-Z][0-9][A-Z])\s*([0-9][A-Z][0-9])\s*$')
def try_postcode_first(request):
    match = r_postcode.search(request.GET['q'].upper())
    if not match:
        return False
    postcode = match.group(1) + match.group(2)
    riding = None
    try:
        riding = postcode_to_riding(postcode)
    except AmbiguousPostcodeException as e:
        # for example, K7L4V3 or J7B1R5
        ec_url = e.ec_url if e.ec_url else EC_POSTCODE_URL % postcode
        return flatpage_response(request, "You’ve got a confusing postcode",
            mark_safe("""Some postal codes might cross riding boundaries. It looks like yours is one of them.
                To find out who your MP is, visit <a href="%s">Elections Canada</a> and
                tell them your full address.""" % ec_url))
    except Exception:
        logger.exception(f"postcode search problem for {postcode}")

    if not riding:
        return flatpage_response(request, "Can’t find that postcode",
            mark_safe("""We’re having trouble figuring out where that postcode is.
                Try asking <a href="http://elections.ca/">Elections Canada</a> who your MP is."""))
    try:
        member = ElectedMember.objects.get(end_date__isnull=True, riding=riding)
        return adaptive_redirect(request, member.politician.get_absolute_url())
    except ElectedMember.DoesNotExist:
        return flatpage_response(request, "Ain’t nobody lookin’ out for you",
            mark_safe("""It looks like that postal code is in the riding of %s. There is no current
            Member of Parliament for that riding. By law, a byelection must be called within
            180 days of a resignation causing a vacancy. (If you think we’ve got our facts
            wrong about your riding or MP, please send an <a class='maillink'>e-mail</a>.)"""
            % riding.dashed_name))
    except ElectedMember.MultipleObjectsReturned:
        raise Exception("Too many MPs for postcode %s" % postcode)
    
def postcode_to_riding(postcode: str) -> Riding | None:
    cached = RidingPostcodeCache.objects.filter(postcode=postcode).first()
    if cached:
        return cached.riding
    
    try:
        riding = postcode_to_riding_ourcommons(postcode)
        if riding:
            RidingPostcodeCache.objects.get_or_create(postcode=postcode, riding=riding, source='ourcommons')
            return riding
    except AmbiguousPostcodeException as e:
        raise
    except Exception:
        logger.exception(f"ourcommons.ca postcode search problem {postcode}")
    
    edid = postcode_to_edid_ec(postcode)
    if edid:
        riding = Riding.objects.get(edid=edid, current=True)
        RidingPostcodeCache.objects.get_or_create(postcode=postcode, riding=riding, source='ec')
        return riding
    
    return None

def postcode_to_edid_represent(postcode):
    url = 'https://represent.opennorth.ca/postcodes/%s/' % postcode.replace(' ', '')
    resp = requests.get(url)
    if resp.status_code != 200:
        return None
    content = resp.json()
    edid = [
        b['external_id'] for b in
        content.get('boundaries_concordance', []) + content.get('boundaries_centroid', [])
        if b['boundary_set_name'] == 'Federal electoral district'
    ]
    return int(edid[0]) if edid else None

class AmbiguousPostcodeException(Exception):

    def __init__(self, postcode, ec_url=None):
        self.postcode = postcode
        self.ec_url = ec_url


EC_POSTCODE_URL = 'https://www.elections.ca/Scripts/vis/FindED?L=e&QID=-1&PAGEID=20&PC=%s'
r_ec_edid = re.compile(r'&ED=(\d{5})&')
def postcode_to_edid_ec(postcode: str) -> int | None:
    resp = requests.get(EC_POSTCODE_URL % postcode.replace(' ', ''), allow_redirects=False,
                        verify=False) # verify=False because EC had some certificate chain issues;
                                      # I think the risk of MITM to return bad riding IDs is low
    if resp.status_code != 302:
        return None
    redirect_url = resp.headers['Location']
    match = r_ec_edid.search(redirect_url)
    if match:
        return int(match.group(1))
    raise AmbiguousPostcodeException(postcode=postcode, ec_url=urljoin(EC_POSTCODE_URL, redirect_url))

def postcode_to_riding_ourcommons(postcode):
    resp = requests.post("https://www.ourcommons.ca/Members/search/members", json={"searchText": postcode})
    resp.raise_for_status()
    content = resp.json()
    if len(content['currentMembers']) == 1:
        riding_name = content['currentMembers'][0]['constituencyNameEn']
    elif len(content['currentMembers']) > 1:
        raise AmbiguousPostcodeException(postcode=postcode)
    elif len(content['currentMembers']) == 0 and content['pastMembers']:
        riding_name = content['pastMembers'][0]['constituencyNameEn']
    else:
        raise Exception(f"Cannot understand ourcommons response for postcode {postcode}")
    
    return Riding.objects.get_by_name(riding_name)

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
        return "https://openparliament.ca/search/?" + urllib.parse.urlencode({'q': query.encode('utf8'), 'sort': 'date desc'})

    def description(self, query):
        return "From openparliament.ca, search results for '%s'" % query

    def items(self, query):
        query_obj = SearchQuery(query, user_params={'sort': 'date desc'})
        return [item for item in query_obj.documents if item['django_ct'] == 'hansards.statement']

    def item_title(self, item):
        return "%s / %s" % (item.get('topic', ''), item.get('politician', ''))

    def item_link(self, item):
        return item['url']

    def item_description(self, item):
        return item['text']

    def item_pubdate(self, item):
        return item['date']
