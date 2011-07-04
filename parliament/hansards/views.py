import datetime
import json
import urllib, urllib2

from django.core.paginator import Paginator, InvalidPage, EmptyPage
from django.conf import settings
from django.http import HttpResponse, Http404, HttpResponseRedirect, HttpResponsePermanentRedirect
from django.shortcuts import get_object_or_404
from django.template import loader, RequestContext
from django.views import generic
from django.views.decorators.vary import vary_on_headers

from parliament.core.utils import get_twitter_share_url
from parliament.hansards.models import Document, Statement

def _get_hansard(hansard_id, hansard_date):
    if hansard_id:
        return get_object_or_404(Document.hansards, pk=hansard_id)
    elif hansard_date:
        try:
            return Document.hansards.get(date=datetime.date(*[int(x) for x in hansard_date.split('-')]))
        except Exception:
            raise Http404
    else:
        raise Exception("hansard() requires an ID or date")

def hansard(request, hansard_id=None, hansard_date=None, sequence=None):
    hansard = _get_hansard(hansard_id, hansard_date)
    return document_view(request, hansard, sequence=sequence)

def document_redirect(request, document_id, sequence=None):
    try:
        document = Document.objects.select_related(
            'committeemeeting', 'committeemeeting__committee').get(
            pk=document_id)
    except Document.DoesNotExist:
        raise Http404
    url = document.get_absolute_url(pretty=True)
    if sequence:
        url += "%s/" % sequence
    return HttpResponsePermanentRedirect(url)

@vary_on_headers('X-Requested-With')
def document_view(request, document, meeting=None, sequence=None):

    per_page = 15
    if 'singlepage' in request.GET:
        per_page = 1500
    
    statement_qs = Statement.objects.filter(document=document)\
        .select_related('member__politician', 'member__riding', 'member__party')
    paginator = Paginator(statement_qs, per_page)

    highlight_statement = None
    try:
        if sequence is not None and 'page' not in request.GET:
            highlight_statement = int(sequence)
            page = int(highlight_statement/per_page) + 1
        else:
            page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1

    # If page request (9999) is out of range, deliver last page of results.
    try:
        statements = paginator.page(page)
    except (EmptyPage, InvalidPage):
        statements = paginator.page(paginator.num_pages)
    
    if highlight_statement is not None:
        try:
            highlight_statement = filter(
                    lambda s: s.sequence == highlight_statement, statements.object_list)[0]
        except IndexError:
            raise Http404
        
    if request.is_ajax():
        t = loader.get_template("hansards/statement_page.inc")
    else:
        if document.document_type == Document.DEBATE:
            t = loader.get_template("hansards/hansard_detail.html")
        elif document.document_type == Document.EVIDENCE:
            t = loader.get_template("committees/meeting.html")

    ctx = {
        'document': document,
        'page': statements,
        'highlight_statement': highlight_statement,
        'singlepage': 'singlepage' in request.GET,
    }
    if document.document_type == Document.DEBATE:
        ctx.update({
            'hansard': document,
            'pagination_url': document.get_absolute_url(),
        })
    elif document.document_type == Document.EVIDENCE:
        ctx.update({
            'meeting': meeting,
            'committee': meeting.committee,
            'pagination_url': meeting.get_absolute_url(),
        })
    return HttpResponse(t.render(RequestContext(request, ctx)))
    
def statement_twitter(request, hansard_id, sequence):
    """Redirects to a Twitter page, prepopulated with sharing info for a particular statement."""
    try:
        statement = Statement.objects.get(document=hansard_id, sequence=sequence)
    except Statement.DoesNotExist:
        raise Http404
        
    if statement.politician:
        description = statement.politician.name
    else:
        description = statement.who
    description += ' on ' + statement.topic
    
    return HttpResponseRedirect(
        get_twitter_share_url(statement.get_absolute_url(), description)
    )
    
def statement_permalink(request, sequence, hansard_id=None, hansard_date=None):
    """A page displaying only a single statement. Used as a non-JS permalink."""
    #TODO: Work with evidence
    
    hansard = _get_hansard(hansard_id, hansard_date)
    statement = get_object_or_404(Statement, document=hansard, sequence=sequence)
    
    if statement.politician:
        who = statement.politician.name
    else:
        who = statement.who
    title = who
    
    if statement.topic:
        title += u' on %s' % statement.topic
    t = loader.get_template("hansards/statement_permalink.html")
    c = RequestContext(request, {
        'title': title,
        'who': who,
        'page': {'object_list': [statement]},
        'statement': statement,
        'hansard': hansard,
        'statements_full_date': True,
        #'statements_context_link': True
    })
    return HttpResponse(t.render(c))
    
def document_cache(request, document_id, language):
    document = get_object_or_404(Document, pk=document_id)
    xmlfile = document.get_cached_xml(language)
    resp = HttpResponse(xmlfile.read(), content_type="text/xml")
    xmlfile.close()
    return resp

def index(request):
    return generic.date_based.archive_index(request,
        queryset=Document.hansards.all(),
        date_field='date',
        num_latest=17,
        template_name="hansards/hansard_archive.html",
        extra_context={'title': 'The Debates of the House of Commons'})

def by_year(request, year):
    return generic.date_based.archive_year(request,
        queryset=Document.hansards.all().order_by('date'),
        date_field='date',
        year=year,
        make_object_list=True,
        extra_context={'title': 'Debates from %s' % year})
