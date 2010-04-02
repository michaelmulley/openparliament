from django.template import Context, loader, RequestContext
from django.http import HttpResponse, Http404, HttpResponseRedirect, HttpResponsePermanentRedirect
from django.contrib.syndication.views import Feed
from django.shortcuts import get_object_or_404
from django.views.generic.list_detail import object_list, object_detail

from parliament.bills.models import Bill, VoteQuestion, MemberVote
from parliament.core.models import Session

def bill(request, bill_id):
    
    bill = get_object_or_404(Bill, pk=bill_id)
    c = RequestContext(request, {
        'bill': bill,
        'statements': bill.statement_set.all().order_by('-time')[:10],
        'votequestions': bill.votequestion_set.all().order_by('-date'),
        'title': 'Bill %s' % bill.number, 
    })
    t = loader.get_template("bills/bill_detail.html")
    return HttpResponse(t.render(c))
    
def index(request):
    sessions = Session.objects.all()
    return object_list(request,
        queryset=Bill.objects.filter(session=sessions[0]),
        extra_context={'session_list': sessions, 'session': sessions[0], 'title': 'Bills & Votes'},
        template_name='bills/index.html')
        
def bills_for_session(request, session_id):
    session = get_object_or_404(Session, pk=session_id)
    bills = Bill.objects.filter(session=session)
    return object_list(request,
        queryset=bills,
        extra_context={'session': session, 'title': 'Bills for the %s' % session})
        
def votes_for_session(request, session_id):
    session = get_object_or_404(Session, pk=session_id)
    return object_list(request,
        queryset=VoteQuestion.objects.filter(session=session),
        extra_context={'session': session, 'title': 'Votes for the %s' % session})
        
def vote(request, vote_id):
    vote = get_object_or_404(VoteQuestion, pk=vote_id)
    membervotes = MemberVote.objects.filter(votequestion=vote)\
        .order_by('member__party', 'member__politician__name_family')\
        .select_related('member', 'member__party', 'member__politician')
    c = RequestContext(request, {
        'vote': vote,
        'membervotes': membervotes,
    })
    t = loader.get_template("bills/votequestion_detail.html")
    return HttpResponse(t.render(c))
    
def all_bills(request):
    return object_list(request, queryset=Bill.objects.all())