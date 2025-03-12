import datetime
from urllib.parse import urlencode

from django.conf import settings
from django.urls import reverse
from django.http import HttpResponse, HttpResponsePermanentRedirect, Http404
from django.shortcuts import get_object_or_404, render
from django.template import loader

from parliament.committees.models import Committee, CommitteeMeeting, CommitteeActivity
from parliament.core.api import ModelListView, ModelDetailView, APIFilters
from parliament.core.models import Session
from parliament.hansards.views import document_view, statement_permalink, statement_ourcommons_redirect
from parliament.hansards.models import Statement, Document
from parliament.text_analysis.models import TextAnalysis
from parliament.text_analysis.views import TextAnalysisView


class CommitteeListView(ModelListView):

    resource_name = 'Committees'

    filters = {
        'session': APIFilters.dbfield('sessions')
    }

    def get_qs(self, request):
        qs = Committee.objects.filter(
            parent__isnull=True, display=True).order_by('name_' + settings.LANGUAGE_CODE)
        if 'session' not in request.GET:
            session = Session.objects.filter(committeeinsession__isnull=False).distinct().order_by('-start')[0]
            qs = qs.filter(sessions=session)
        return qs

    def get_html(self, request):
        committees = self.get_qs(request)
        recent_meetings = CommitteeMeeting.objects.order_by('-date')[:50]
        recent_studies = CommitteeActivity.objects.filter(
            study=True,
            committeemeeting__in=list(recent_meetings.values_list('id', flat=True))
        ).distinct()[:12]
        return render(request, "committees/committee_list.html", {
            'object_list': committees,
            'title': 'House Committees',
            'recent_studies': recent_studies
        })
committee_list = CommitteeListView.as_view()

def committee_id_redirect(request, committee_id):
    committee = get_object_or_404(Committee, pk=committee_id)
    return HttpResponsePermanentRedirect(request.path.replace(committee_id, committee.slug, 1))

class CommitteeView(ModelDetailView):

    resource_name = 'Committee'

    def get_object(self, request, slug):
        return get_object_or_404(Committee, slug=slug)

    def get_related_resources(self, request, qs, result):
        return {
            'meetings_url': reverse('committee_meetings') + '?' +
                urlencode({'committee': self.kwargs['slug']}),
            'committees_url': reverse('committee_list')
        }

    def get_html(self, request, slug):
        cmte = self.get_object(request, slug)
        recent_meetings = list(CommitteeMeeting.objects.filter(committee=cmte).order_by('-date')[:20])
        recent_studies = CommitteeActivity.objects.filter(
            study=True,
            committeemeeting__in=recent_meetings
        ).distinct()

        oldest_year = newest_year = meeting_years = None
        try:
            oldest_year = CommitteeMeeting.objects.filter(committee=cmte).order_by('date')[0].date.year
            newest_year = recent_meetings[0].date.year
            meeting_years = reversed(list(range(oldest_year, newest_year+1)))
        except IndexError:
            pass

        title = cmte.name
        if 'Committee' not in title and not cmte.parent:
            title += ' Committee'

        t = loader.get_template("committees/committee_detail.html")
        c = {
            'title': title,
            'committee': cmte,
            'meetings': recent_meetings,
            'recent_studies': recent_studies,
            'archive_years': meeting_years,
            'subcommittees': Committee.objects.filter(parent=cmte, display=True, sessions=Session.objects.current()),
            'include_year': newest_year != datetime.date.today().year,
            'search_placeholder': "Search %s transcripts" % cmte.short_name,
            'wordcloud_js': TextAnalysis.objects.get_wordcloud_js(
                reverse('committee_analysis', kwargs={'committee_slug': slug})),
        }
        return HttpResponse(t.render(c, request))
committee = CommitteeView.as_view()        

def committee_year_archive(request, slug, year):
    cmte = get_object_or_404(Committee, slug=slug)
    year = int(year)

    meetings = list(
        CommitteeMeeting.objects.filter(committee=cmte, date__year=year).order_by('date')
    )
    studies = CommitteeActivity.objects.filter(
        study=True,
        committeemeeting__in=meetings
    ).distinct()

    return render(request, "committees/committee_year_archive.html", {
        'title': "%s Committee in %s" % (cmte, year),
        'committee': cmte,
        'meetings': meetings,
        'studies': studies,
        'year': year
    })
    
def committee_activity(request, activity_id):
    activity = get_object_or_404(CommitteeActivity, id=activity_id)

    return render(request, "committees/committee_activity.html", {
        'title': str(activity),
        'activity': activity,
        'meetings': activity.committeemeeting_set.order_by('-date'),
        'committee': activity.committee
    })

def _get_meeting(committee_slug, session_id, number):
    try:
        return CommitteeMeeting.objects.select_related('evidence', 'committee').get(
            committee__slug=committee_slug, session=session_id, number=number)
    except CommitteeMeeting.DoesNotExist:
        raise Http404

class CommitteeMeetingListView(ModelListView):

    resource_name = 'Committee meetings'

    filters = {
        'number': APIFilters.dbfield(filter_types=APIFilters.numeric_filters,
            help="each meeting in a session is given a sequential #"),
        'session': APIFilters.dbfield(help="e.g. 41-1"),
        'date': APIFilters.dbfield(filter_types=APIFilters.numeric_filters,
            help="e.g. date__gt=2010-01-01"),
        'in_camera': APIFilters.dbfield(help="closed to the public? True, False"),
        'committee': APIFilters.fkey(lambda u: {'committee__slug': u[-1]},
            help="e.g. /committees/aboriginal-affairs")
    }

    def get_qs(self, request):
        return CommitteeMeeting.objects.all().order_by('-date')


class CommitteeMeetingView(ModelDetailView):

    resource_name = 'Committee meeting'

    def get_object(self, request, committee_slug, session_id, number):
        return _get_meeting(committee_slug, session_id, number)

    def get_related_resources(self, request, obj, result):
        if obj.evidence_id:
            return {
                'speeches_url': reverse('speeches') + '?' +
                    urlencode({'document': result['url']})
            }

    def get_html(self, request, committee_slug, session_id, number, slug=None):
        meeting = self.get_object(request, committee_slug, session_id, number)

        document = meeting.evidence
        if document:
            return document_view(request, document, meeting=meeting, slug=slug)
        else:
            return render(request, "committees/meeting.html", {
                'meeting': meeting,
                'committee': meeting.committee
            })
committee_meeting = CommitteeMeetingView.as_view()

def evidence_ourcommons_redirect(request, committee_slug, session_id, number, slug):
    meeting = _get_meeting(committee_slug, session_id, number)
    return statement_ourcommons_redirect(meeting.evidence, slug)

class EvidenceAnalysisView(TextAnalysisView):

    def get_qs(self, request, **kwargs):
        m = _get_meeting(**kwargs)
        if not m.evidence:
            raise Http404
        qs = m.evidence.statement_set.all()
        request.evidence = m.evidence
        # if 'party' in request.GET:
        #     qs = qs.filter(member__party__slug=request.GET['party'])
        return qs

    def get_corpus_name(self, request, committee_slug, **kwargs):
        return committee_slug

    def get_analysis(self, request, **kwargs):
        analysis = super(EvidenceAnalysisView, self).get_analysis(request, **kwargs)
        word = analysis.top_word
        if word and word != request.evidence.most_frequent_word:
            Document.objects.filter(id=request.evidence.id).update(most_frequent_word=word)
        return analysis

evidence_analysis = EvidenceAnalysisView.as_view()

class CommitteeAnalysisView(TextAnalysisView):

    expiry_days = 7

    def get_corpus_name(self, request, committee_slug):
        return committee_slug

    def get_qs(self, request, committee_slug):
        cmte = get_object_or_404(Committee, slug=committee_slug)
        qs = Statement.objects.filter(
            document__document_type='E',
            time__gte=datetime.datetime.now() - datetime.timedelta(days=30 * 6),
            document__committeemeeting__committee=cmte
        )
        return qs

class CommitteeMeetingStatementView(ModelDetailView):

    resource_name = 'Speech (committee meeting)'

    def get_object(self, request, committee_slug, session_id, number, slug):
        meeting = _get_meeting(committee_slug, session_id, number)
        return meeting.evidence.statement_set.get(slug=slug)

    def get_related_resources(self, request, qs, result):
        return {
            'document_speeches_url': reverse('speeches') + '?' +
                urlencode({'document': result['document_url']}),
        }        

    def get_html(self, request, **kwargs):
        return committee_meeting(request, **kwargs)
committee_meeting_statement = CommitteeMeetingStatementView.as_view()


def evidence_permalink(request, committee_slug, session_id, number, slug):

    try:
        meeting = CommitteeMeeting.objects.select_related('evidence', 'committee').get(
            committee__slug=committee_slug, session=session_id, number=number)
    except CommitteeMeeting.DoesNotExist:
        raise Http404

    doc = meeting.evidence
    statement = get_object_or_404(Statement, document=doc, slug=slug)

    return statement_permalink(request, doc, statement, "committees/evidence_permalink.html",
        meeting=meeting, committee=meeting.committee)



