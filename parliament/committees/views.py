from django.http import HttpResponse, HttpResponsePermanentRedirect
from django.shortcuts import get_object_or_404, render
from django.template import loader, RequestContext

from parliament.committees.models import Committee, CommitteeMeeting, CommitteeActivity
from parliament.core.models import Session
from parliament.hansards.views import document_view

def committee_list(request):
    committees = Committee.objects.filter(sessions=Session.objects.current(),
        parent__isnull=True)

    recent_meetings = CommitteeMeeting.objects.order_by('-date')[:20]
    recent_studies = CommitteeActivity.objects.filter(
        study=True,
        committeemeeting__in=list(recent_meetings.values_list('id', flat=True))
    ).distinct()
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

    t = loader.get_template("committees/committee_detail.html")
    c = RequestContext(request, {
        'title': cmte.name,
        'committee': cmte,
        'meetings': cmte.committeemeeting_set.order_by('-date')
    })
    return HttpResponse(t.render(c))
    
def activity(request, committee_id, activity_id):
    pass

def committee_meeting(request, committee_slug, session_id, number, slug=None):
    meeting = get_object_or_404(CommitteeMeeting, committee__slug=committee_slug,
        session=session_id, number=number)

    document = meeting.evidence
    if document:
        return document_view(request, document, meeting=meeting, slug=slug)
    else:
        return HttpResponse("No evidence")



