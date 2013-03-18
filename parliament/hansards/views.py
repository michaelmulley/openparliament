import datetime
from urllib import urlencode

from django.core.paginator import Paginator, InvalidPage, EmptyPage
from django.core import urlresolvers
from django.http import HttpResponse, Http404, HttpResponsePermanentRedirect, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template import loader, RequestContext
from django.views.generic.dates import (ArchiveIndexView, YearArchiveView, MonthArchiveView)
from django.views.decorators.vary import vary_on_headers

from parliament.committees.models import CommitteeMeeting
from parliament.core.api import ModelDetailView, ModelListView, APIFilters
from parliament.hansards.models import Document, Statement

def _get_hansard(year, month, day):
    return get_object_or_404(Document.debates,
        date=datetime.date(int(year), int(month), int(day)))

class HansardView(ModelDetailView):

    resource_name = 'House debates'

    def get_object(self, request, **kwargs):
        return _get_hansard(**kwargs)

    def get_html(self, request, **kwargs):
        return document_view(request, _get_hansard(**kwargs))

    def get_related_resources(self, request, obj, result):
        return {
            'speeches_url': urlresolvers.reverse('speeches') + '?' +
                urlencode({'document': result['object']['url']}),
            'debates_url': urlresolvers.reverse('debates')
        }
hansard = HansardView.as_view()


class HansardStatementView(ModelDetailView):

    resource_name = 'Speech (House debate)'

    def get_object(self, request, year, month, day, slug):
        date = datetime.date(int(year), int(month), int(day))
        return Statement.objects.get(
            document__document_type='D',
            document__date=date,
            slug=slug
        )

    def get_related_resources(self, request, qs, result):
        parent_kwargs = dict(self.kwargs)
        parent_kwargs.pop('slug')
        return {
            'speeches_url': urlresolvers.reverse('debate_speeches', kwargs=parent_kwargs),
            'hansard_url': urlresolvers.reverse('debate', kwargs=parent_kwargs)
        }

    def get_html(self, request, year, month, day, slug):
        return document_view(request, _get_hansard(year, month, day), slug=slug)
hansard_statement = HansardStatementView.as_view()

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
        per_page = 50000
    
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


class SpeechesView(ModelListView):

    def document_filter(qs, view, filter_name, filter_extra, val):
        u = val.rstrip('/').split('/')
        if u[-4] == 'debates':
            # /debates/2013/2/15/
            date = datetime.date(int(u[-3]), int(u[-2]), int(u[-1]))
            return qs.filter(
                document__document_type='D',
                document__date=date
            ).order_by('sequence')
        elif u[-4] == 'committees':
            # /commmittees/national-defence/41-1/63/
            meeting = CommitteeMeeting.objects.get(
                committee__slug=u[-3], session=u[-2], number=u[-1])
            return qs.filter(document=meeting.evidence_id).order_by('sequence')

    filters = {
        'procedural': APIFilters.dbfield(),
        'document': document_filter
    }

    resource_name = 'Speeches'

    def get_qs(self, request):
        qs = Statement.objects.all().prefetch_related('politician')
        if 'document' not in request.GET:
            qs = qs.order_by('-time')
        return qs
speeches = SpeechesView.as_view()

class DebatePermalinkView(ModelDetailView):

    def _get_objs(self, request, slug, year, month, day):
        doc = _get_hansard(year, month, day)
        if slug.isdigit():
            statement = get_object_or_404(Statement, document=doc, sequence=slug)
        else:
            statement = get_object_or_404(Statement, document=doc, slug=slug)
        return doc, statement

    def get_json(self, request, **kwargs):
        url = self._get_objs(request, **kwargs)[1].get_absolute_url()
        return HttpResponseRedirect(url + '?' + request.GET.urlencode())

    def get_html(self, request, **kwargs):
        doc, statement = self._get_objs(request, **kwargs)
        return statement_permalink(request, doc, statement, "hansards/statement_permalink.html",
            hansard=doc)
debate_permalink = DebatePermalinkView.as_view()

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

class APIArchiveView(ModelListView):

    resource_name = 'House debates'

    def get_html(self, request, **kwargs):
        return self.get(request, **kwargs)

    def get_qs(self, request, **kwargs):
        return self.get_dated_items()[1]

class DebateIndexView(TitleAdder, ArchiveIndexView, APIArchiveView):
    queryset = Document.debates.all()
    date_field = 'date'
    template_name = "hansards/hansard_archive.html"
    page_title='The Debates of the House of Commons'
index = DebateIndexView.as_view()

class DebateYearArchive(TitleAdder, YearArchiveView, APIArchiveView):
    queryset = Document.debates.all().order_by('date')
    date_field = 'date'
    make_object_list = True
    template_name = "hansards/hansard_archive_year.html"
    page_title = lambda self: 'Debates from %s' % self.get_year()
by_year = DebateYearArchive.as_view()

class DebateMonthArchive(TitleAdder, MonthArchiveView, APIArchiveView):
    queryset = Document.debates.all().order_by('date')
    date_field = 'date'
    make_object_list = True
    month_format = "%m"
    template_name = "hansards/hansard_archive_year.html"
    page_title = lambda self: 'Debates from %s' % self.get_year()
by_month = DebateMonthArchive.as_view()