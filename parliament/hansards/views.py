import datetime
from urllib import urlencode

from django.core.paginator import Paginator, InvalidPage, EmptyPage
from django.core import urlresolvers
from django.http import HttpResponse, Http404, HttpResponsePermanentRedirect, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template import loader
from django.views.generic.dates import (ArchiveIndexView, YearArchiveView, MonthArchiveView)
from django.views.decorators.vary import vary_on_headers

from parliament.committees.models import CommitteeMeeting
from parliament.core.api import ModelDetailView, ModelListView, APIFilters, BadRequest
from parliament.hansards.models import Document, Statement
from parliament.text_analysis.models import TextAnalysis
from parliament.text_analysis.views import TextAnalysisView

def _get_hansard(year, month, day):
    return get_object_or_404(Document.debates,
        date=datetime.date(int(year), int(month), int(day)))

class HansardView(ModelDetailView):

    resource_name = 'House debate'

    def get_object(self, request, **kwargs):
        return _get_hansard(**kwargs)

    def get_html(self, request, **kwargs):
        return document_view(request, _get_hansard(**kwargs))

    def get_related_resources(self, request, obj, result):
        return {
            'speeches_url': urlresolvers.reverse('speeches') + '?' +
                urlencode({'document': result['url']}),
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
        return {
            'document_speeches_url': urlresolvers.reverse('speeches') + '?' +
                urlencode({'document': result['document_url']}),
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

    per_page = 25
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
        
    ctx = {
        'document': document,
        'page': statements,
        'highlight_statement': highlight_statement,
        'singlepage': 'singlepage' in request.GET,
        'allow_single_page': True
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

    if request.is_ajax():
        t = loader.get_template("hansards/statement_page.inc")
    else:
        if document.document_type == Document.DEBATE:
            t = loader.get_template("hansards/hansard_detail.html")
        elif document.document_type == Document.EVIDENCE:
            t = loader.get_template("committees/meeting_evidence.html")
        ctx['wordcloud_js'] = TextAnalysis.objects.get_wordcloud_js(
            key=document.get_text_analysis_url())

    return HttpResponse(t.render(ctx, request))


class SpeechesView(ModelListView):

    def document_filter(qs, view, filter_name, filter_extra, val):
        u = val.rstrip('/').split('/')
        if u[-4] == 'debates':
            # /debates/2013/2/15/
            try:
                date = datetime.date(int(u[-3]), int(u[-2]), int(u[-1]))
            except ValueError:
                raise BadRequest("Invalid document URL")
            return qs.filter(
                document__document_type='D',
                document__date=date
            ).order_by('sequence')
        elif u[-4] == 'committees':
            # /commmittees/national-defence/41-1/63/
            try:
                meeting = CommitteeMeeting.objects.get(
                    committee__slug=u[-3], session=u[-2], number=u[-1])
            except (ValueError, CommitteeMeeting.DoesNotExist):
                raise BadRequest("Invalid debate/meeting URL")
            return qs.filter(document=meeting.evidence_id).order_by('sequence')
    document_filter.help = "the URL of the debate or committee meeting"

    filters = {
        'procedural': APIFilters.dbfield(help="is this a short, routine procedural speech? True or False"),
        'document': document_filter,
        'politician': APIFilters.politician(),
        'politician_membership': APIFilters.fkey(lambda u: {'member': u[-1]}),
        'time': APIFilters.dbfield(filter_types=APIFilters.numeric_filters,
            help="e.g. time__range=2012-10-19 10:00,2012-10-19 11:00"),
        'mentioned_politician': APIFilters.politician('mentioned_politicians'),
        'mentioned_bill': APIFilters.fkey(lambda u: {
            'bills__billinsession__session': u[-2],
            'bills__number': u[-1]
        }, help="e.g. /bills/41-1/C-14/")
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
    return HttpResponse(t.render(ctx, request))
    
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

    filters = {
        'session': APIFilters.dbfield(help='e.g. 41-1'),
        'date': APIFilters.dbfield(filter_types=APIFilters.numeric_filters,
            help='e.g. date__range=2010-01-01,2010-09-01'),
        'number': APIFilters.dbfield(help='each Hansard in a session is given a sequential #'),
    }

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

class HansardAnalysisView(TextAnalysisView):

    def get_corpus_name(self, request, year, **kwargs):
        # Use a special corpus for old debates
        if int(year) < (datetime.date.today().year - 1):
            return 'debates-%s' % year
        return 'debates'

    def get_qs(self, request, **kwargs):
        h = _get_hansard(**kwargs)
        request.hansard = h
        qs = h.statement_set.all()
        # if 'party' in request.GET:
            # qs = qs.filter(member__party__slug=request.GET['party'])
        return qs

    def get_analysis(self, request, **kwargs):
        analysis = super(HansardAnalysisView, self).get_analysis(request, **kwargs)
        word = analysis.top_word
        if word and word != request.hansard.most_frequent_word:
            Document.objects.filter(id=request.hansard.id).update(most_frequent_word=word)
        return analysis

hansard_analysis = HansardAnalysisView.as_view()