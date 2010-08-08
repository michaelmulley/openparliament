import json
import urllib, urllib2

from django.template import Context, loader, RequestContext
from django.http import HttpResponse, Http404, HttpResponseRedirect, HttpResponsePermanentRedirect
from django.views import generic
from django.core.paginator import Paginator, InvalidPage, EmptyPage
from django.conf import settings
from django.shortcuts import get_object_or_404

from parliament.hansards.models import Hansard, HansardCache, Statement

def hansard(request, hansard_id, statement_seq=None):
    PER_PAGE = 15
    hansard = get_object_or_404(Hansard, pk=hansard_id)
    statement_qs = Statement.objects.filter(hansard=hansard).select_related('member__politician', 'member__riding', 'member__party')
    paginator = Paginator(statement_qs, PER_PAGE)

    highlight_statement = None
    try:
        if statement_seq and 'page' not in request.GET:
            highlight_statement = int(statement_seq)
            page = int(highlight_statement/PER_PAGE) + 1
        else:
            page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1

    # If page request (9999) is out of range, deliver last page of results.
    try:
        statements = paginator.page(page)
    except (EmptyPage, InvalidPage):
        statements = paginator.page(paginator.num_pages)
    
    if highlight_statement:
        try:
            highlight_statement = filter(lambda s: s.sequence == highlight_statement, statements.object_list)[0]
        except IndexError:
            raise Http404
        
    if request.is_ajax():
        t = loader.get_template("hansards/statement_page.inc")
    else:
        t = loader.get_template("hansards/hansard_detail.html")
    c = RequestContext(request, {
        'hansard': hansard,
        'page': statements,
        'highlight_statement': highlight_statement,
        'pagination_url': hansard.get_absolute_url(),
    })
    return HttpResponse(t.render(c))
    
def statement_twitter(request, hansard_id, statement_seq):
    """Redirects to a Twitter page, prepopulated with sharing info for a particular statement."""
    try:
        statement = Statement.objects.get(hansard=hansard_id, sequence=statement_seq)
    except Statement.DoesNotExist:
        raise Http404
    
    longurl = settings.SITE_URL + statement.get_absolute_url()
    
    shorten_resp_raw = urllib2.urlopen(settings.BITLY_API_URL + urllib.urlencode({'longurl': longurl}))
    shorten_resp = json.load(shorten_resp_raw)
    
    shorturl = shorten_resp['data']['url']
    
    description = u'%s on %s' % (statement.politician.name, statement.topic)
    if (len(description) + len(shorturl)) > 139:
        description = description[:136-len(shorturl)] + '...'
    message = "%s %s" % (description, shorturl)
    return HttpResponseRedirect('http://twitter.com/home?' + urllib.urlencode({'status': message}))
    
def statement_permalink(request, hansard_id, statement_seq):
    """A page displaying only a single statement. Used as a non-JS permalink."""
    try:
        statement = Statement.objects.get(hansard=hansard_id, sequence=statement_seq)
    except Statement.DoesNotExist:
        raise Http404
        
    title = statement.politician.name
    if statement.topic:
        title += u' on %s' % statement.topic
    t = loader.get_template("hansards/statement_permalink.html")
    c = RequestContext(request, {
        'title': title,
        'page': {'object_list': [statement]},
        'statement': statement,
        'hansard': statement.hansard,
        'statements_full_date': True,
        'statements_context_link': True
    })
    return HttpResponse(t.render(c))
    
def hansardcache (request, hansard_id):
    cache = HansardCache.objects.get(hansard=hansard_id)
    return HttpResponse(cache.getHTML())
    
def index(request):
    return generic.date_based.archive_index(request, 
        queryset=Hansard.objects.all(), 
        date_field='date',
        num_latest=17,
        extra_context={'title': 'The Debates of the House of Commons'})
        
def by_year(request, year):
    return generic.date_based.archive_year(request,
        queryset=Hansard.objects.all().order_by('date'),
        date_field='date',
        year=year,
        make_object_list=True,
        extra_context={'title': 'Debates from %s' % year})
