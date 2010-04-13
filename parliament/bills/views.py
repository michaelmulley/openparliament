import datetime

from django.template import Context, loader, RequestContext
from django.http import HttpResponse, Http404, HttpResponseRedirect, HttpResponsePermanentRedirect
from django.contrib.syndication.views import Feed
from django.shortcuts import get_object_or_404
from django.views.generic.list_detail import object_list, object_detail
from django.core.paginator import Paginator, InvalidPage, EmptyPage
from django.contrib.syndication.views import Feed
from django.template.defaultfilters import date as format_date

from parliament.bills.models import Bill, VoteQuestion, MemberVote
from parliament.core.models import Session
from parliament.hansards.models import Statement

def bill(request, bill_id):
    PER_PAGE = 10
    bill = get_object_or_404(Bill, pk=bill_id)
    statements = bill.statement_set.all().order_by('-time', '-sequence').select_related('member', 'member__politician', 'member__riding', 'member__party')
    paginator = Paginator(statements, PER_PAGE)

    try:
        pagenum = int(request.GET.get('page', '1'))
    except ValueError:
        pagenum = 1
    try:
        page = paginator.page(pagenum)
    except (EmptyPage, InvalidPage):
        page = paginator.page(paginator.num_pages)

    c = RequestContext(request, {
        'bill': bill,
        'page': page,
        'votequestions': bill.votequestion_set.all().order_by('-date'),
        'title': 'Bill %s' % bill.number, 
        'statements_full_date': True,
        'statements_context_link': True,
    })
    if request.is_ajax():
        t = loader.get_template("hansards/statement_page.inc")
    else:
        t = loader.get_template("bills/bill_detail.html")
    return HttpResponse(t.render(c))
    
def index(request):
    sessions = Session.objects.with_bills().distinct()
    len(sessions) # evaluate it
    return object_list(request,
        queryset=Bill.objects.filter(sessions=sessions[0]),
        extra_context={'session_list': sessions, 'session': sessions[0], 'title': 'Bills & Votes'},
        template_name='bills/index.html')
        
def bills_for_session(request, session_id):
    session = get_object_or_404(Session, pk=session_id)
    bills = Bill.objects.filter(sessions=session)
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
    
class BillFeed(Feed):

    def get_object(self, request, bill_id):
        return get_object_or_404(Bill, pk=bill_id)

    def title(self, bill):
        return "Bill %s" % bill.number

    def link(self, bill):
        return "http://openparliament.ca" + bill.get_absolute_url()

    def description(self, bill):
        return "From openparliament.ca, speeches about Bill %s, %s" % (bill.number, bill.name)

    def items(self, bill):
        statements = bill.statement_set.all().order_by('-time', '-sequence').select_related('member', 'member__politician', 'member__riding', 'member__party')[:10]
        votes = bill.votequestion_set.all().order_by('-date', '-number')[:3]
        merged = list(votes) + list(statements)
        merged.sort(key=lambda i: i.date, reverse=True)
        return merged

    def item_title(self, item):
        if isinstance(item, VoteQuestion):
            return "Vote #%s (%s)" % (item.number, item.get_result_display())
        else:
            return "%(name)s (%(party)s%(date)s)" % {
                'name': item.name_info['display_name'],
                'party': item.member.party.short_name + '; ' if item.member else '',
                'date': format_date(item.time, "F jS"),
            }

    def item_link(self, item):
        return item.get_absolute_url()

    def item_description(self, item):
        if isinstance(item, Statement):
            return item.text_html()
        else:
            return item.description

    def item_pubdate(self, item):
        return datetime.datetime(item.date.year, item.date.month, item.date.day)
