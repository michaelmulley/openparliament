import datetime

from django.http import HttpResponse, HttpResponsePermanentRedirect, Http404
from django.shortcuts import get_object_or_404, render
from django.template import loader, RequestContext
from django.core.serializers.json import simplejson as json

from parliament.committees.models import Committee, CommitteeMeeting, CommitteeActivity
from parliament.core.models import Session
from parliament.hansards.views import document_view, statement_permalink
from parliament.hansards.models import Statement

def committee_list(request):
    committees = Committee.objects.filter(sessions=Session.objects.current(),
        parent__isnull=True)

    if request.GET.get('format') == 'json':
        # This is a one-off hack, to later be replaced by nicer general-purpose JSON code
        resp = HttpResponse(mimetype='application/json')
        json.dump(list(committees.order_by('name').values('name', 'slug')), resp)
        return resp

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

def committee_id_redirect(request, committee_id):
    committee = get_object_or_404(Committee, pk=committee_id)
    return HttpResponsePermanentRedirect(request.path.replace(committee_id, committee.slug, 1))

def committee(request, slug):
    cmte = get_object_or_404(Committee, slug=slug)

    recent_meetings = list(CommitteeMeeting.objects.filter(committee=cmte).order_by('-date')[:20])
    recent_studies = CommitteeActivity.objects.filter(
        study=True,
        committeemeeting__in=recent_meetings
    ).distinct()

    oldest_year = CommitteeMeeting.objects.order_by('date')[0].date.year
    newest_year = recent_meetings[0].date.year
    meeting_years = reversed(range(oldest_year, newest_year+1))

    title = cmte.name
    if not cmte.parent:
        title += u' Committee'

    t = loader.get_template("committees/committee_detail.html")
    c = RequestContext(request, {
        'title': title,
        'committee': cmte,
        'meetings': recent_meetings,
        'recent_studies': recent_studies,
        'archive_years': meeting_years,
        'subcommittees': Committee.objects.filter(parent=cmte, sessions=Session.objects.current()),
        'include_year': newest_year != datetime.date.today().year,
        'search_placeholder': u"Search %s transcripts" % cmte.short_name
    })
    return HttpResponse(t.render(c))

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
        'title': u"%s Committee in %s" % (cmte, year),
        'committee': cmte,
        'meetings': meetings,
        'studies': studies,
        'year': year
    })
    
def committee_activity(request, activity_id):
    activity = get_object_or_404(CommitteeActivity, id=activity_id)

    return render(request, "committees/committee_activity.html", {
        'title': unicode(activity),
        'activity': activity,
        'meetings': activity.committeemeeting_set.order_by('-date'),
        'committee': activity.committee
    })

def committee_meeting(request, committee_slug, session_id, number, slug=None):
    meeting = get_object_or_404(CommitteeMeeting, committee__slug=committee_slug,
        session=session_id, number=number)

    document = meeting.evidence
    if document:
        return document_view(request, document, meeting=meeting, slug=slug)
    else:
        return render(request, "committees/meeting.html", {
            'meeting': meeting,
            'committee': meeting.committee
        })

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



