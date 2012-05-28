import datetime
import json
import urllib, urllib2

from django.core.paginator import Paginator, InvalidPage, EmptyPage
from django.conf import settings
from django.http import HttpResponse, Http404, HttpResponseRedirect, HttpResponsePermanentRedirect
from django.shortcuts import get_object_or_404
from django.template import loader, RequestContext
from django.views.generic.dates import (ArchiveIndexView, YearArchiveView, MonthArchiveView)
from django.views.decorators.vary import vary_on_headers

from parliament.core.utils import get_twitter_share_url
from parliament.hansards.models import Document, Statement

def _get_hansard(year, month, day):
    return get_object_or_404(Document.debates,
        date=datetime.date(int(year), int(month), int(day)))

def hansard(request, year, month, day, slug=None):
    return document_view(request, _get_hansard(year, month, day), slug=slug)

def document_redirect(request, document_id, slug=None):
    try:
        document = Document.objects.select_related(
            'committeemeeting', 'committeemeeting__committee').get(
            pk=document_id)
    except Document.DoesNotExist:
        raise Http404
    url = document.get_absolute_url()
    if slug:
        url += "%s/" % slug
    return HttpResponsePermanentRedirect(url)

@vary_on_headers('X-Requested-With')
def document_view(request, document, meeting=None, slug=None):

    per_page = 15
    if 'singlepage' in request.GET:
        per_page = 1500
    
    statement_qs = Statement.objects.filter(document=document)\
        .select_related('member__politician', 'member__riding', 'member__party')
    paginator = Paginator(statement_qs, per_page)

    highlight_statement = None
    try:
        if slug is not None and 'page' not in request.GET:
            if slug.isdigit():
                highlight_statement = int(slug)
            else:
                highlight_statement = statement_qs.filter(slug=slug).values_list('sequence', flat=True)[0]
            page = int(highlight_statement/per_page) + 1
        else:
            page = int(request.GET.get('page', '1'))
    except (ValueError, IndexError):
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
            t = loader.get_template("committees/meeting_evidence.html")

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
    
def debate_permalink(request, slug, year, month, day):

    doc = _get_hansard(year, month, day)
    if slug.isdigit():
        statement = get_object_or_404(Statement, document=doc, sequence=slug)
    else:
        statement = get_object_or_404(Statement, document=doc, slug=slug)

    return statement_permalink(request, doc, statement, "hansards/statement_permalink.html",
        hansard=doc)

def statement_permalink(request, doc, statement, template, **kwargs):
    """A page displaying only a single statement. Used as a non-JS permalink."""

    if statement.politician:
        who = statement.politician.name
    else:
        who = statement.who
    title = who
    
    if statement.topic:
        title += u' on %s' % statement.topic
    elif 'committee' in kwargs:
        title += u' at the ' + kwargs['committee'].title

    t = loader.get_template(template)
    ctx = {
        'title': title,
        'who': who,
        'page': {'object_list': [statement]},
        'doc': doc,
        'statement': statement,
        'statements_full_date': True,
        'statement_url': statement.get_absolute_url(),
        #'statements_context_link': True
    }
    ctx.update(kwargs)
    return HttpResponse(t.render(RequestContext(request, ctx)))
    
def document_cache(request, document_id, language):
    document = get_object_or_404(Document, pk=document_id)
    xmlfile = document.get_cached_xml(language)
    resp = HttpResponse(xmlfile.read(), content_type="text/xml")
    xmlfile.close()
    return resp

class TitleAdder(object):

    def get_context_data(self, **kwargs):
        context = super(TitleAdder, self).get_context_data(**kwargs)
        context.update(title=self.page_title)
        return context

class DebateIndexView(TitleAdder, ArchiveIndexView):
    queryset = Document.debates.all()
    date_field = 'date'
    template_name = "hansards/hansard_archive.html"
    page_title='The Debates of the House of Commons'
index = DebateIndexView.as_view()

class DebateYearArchive(TitleAdder, YearArchiveView):
    queryset = Document.debates.all().order_by('date')
    date_field = 'date'
    make_object_list = True
    template_name = "hansards/hansard_archive_year.html"
    page_title = lambda self: 'Debates from %s' % self.get_year()
by_year = DebateYearArchive.as_view()

class DebateMonthArchive(TitleAdder, MonthArchiveView):
    queryset = Document.debates.all().order_by('date')
    date_field = 'date'
    make_object_list = True
    month_format = "%m"
    template_name = "hansards/hansard_archive_year.html"
    page_title = lambda self: 'Debates from %s' % self.get_year()
by_month = DebateMonthArchive.as_view()