import datetime
from urllib import urlencode

from django.contrib.syndication.views import Feed
from django.core import urlresolvers
from django.core.paginator import Paginator, InvalidPage, EmptyPage
from django.http import HttpResponse, Http404, HttpResponseRedirect, HttpResponsePermanentRedirect
from django.shortcuts import get_object_or_404
from django.template import loader
from django.template.defaultfilters import date as format_date
from django.utils.safestring import mark_safe
from django.views.decorators.vary import vary_on_headers

from parliament.bills.models import Bill, VoteQuestion, MemberVote, BillInSession
from parliament.core.api import ModelListView, ModelDetailView, APIFilters
from parliament.core.models import Session
from parliament.hansards.models import Statement, Document

def bill_pk_redirect(request, bill_id):
    bill = get_object_or_404(Bill, pk=bill_id)
    return HttpResponsePermanentRedirect(
        urlresolvers.reverse('bill', kwargs={
        'session_id': bill.get_session().id, 'bill_number': bill.number}))


class BillDetailView(ModelDetailView):

    resource_name = 'Bill'

    def get_object(self, request, session_id, bill_number):
        return BillInSession.objects.select_related(
            'bill', 'sponsor_politician').get(session=session_id, bill__number=bill_number)

    def get_related_resources(self, request, qs, result):
        return {
            'bills_url': urlresolvers.reverse('bills')
        }

    def _render_page(self, request, qs, per_page=10):
        paginator = Paginator(qs, per_page)

        try:
            pagenum = int(request.GET.get('page', '1'))
        except ValueError:
            pagenum = 1
        try:
            return paginator.page(pagenum)
        except (EmptyPage, InvalidPage):
            return paginator.page(paginator.num_pages)

    def get_html(self, request, session_id, bill_number):
        bill = get_object_or_404(Bill, sessions=session_id, number=bill_number)

        mentions = bill.statement_set.all().order_by('-time', '-sequence').select_related('member', 'member__politician', 'member__riding', 'member__party')
        major_speeches = bill.get_major_speeches().order_by('-document__date', 'sequence').select_related(
            'member', 'member__politician', 'member__riding', 'member__party')
        meetings = bill.get_committee_meetings()

        tab = request.GET.get('tab', 'major-speeches')

        has_major_speeches = major_speeches.exists()
        has_mentions = has_major_speeches or mentions.exists()
        has_meetings = meetings.exists()

        if tab == 'major-speeches' and not has_major_speeches:
            tab = 'mentions'

        per_page = 500 if request.GET.get('singlepage') else 15

        if tab == 'mentions':
            page = self._render_page(request, mentions, per_page=per_page)
        elif tab == 'major-speeches':
            page = self._render_page(request, major_speeches, per_page=per_page)
        else:
            page = None

        c = {
            'bill': bill,
            'has_major_speeches': has_major_speeches,
            'has_mentions': has_mentions,
            'has_meetings': has_meetings,
            'committee_meetings': meetings,
            'votequestions': bill.votequestion_set.all().order_by('-date', '-number'),
            'page': page,
            'allow_single_page': True,
            'tab': tab,
            'title': ('Bill %s' % bill.number) + (' (Historical)' if bill.session.end else ''),
            'statements_full_date': True,
            'statements_context_link': True,
        }
        if request.is_ajax():
            if tab == 'meetings':
                t = loader.get_template("bills/related_meetings.inc")
            else:
                t = loader.get_template("hansards/statement_page.inc")
        else:
            t = loader.get_template("bills/bill_detail.html")
        return HttpResponse(t.render(c, request))
bill = vary_on_headers('X-Requested-With')(BillDetailView.as_view())
    
class BillListView(ModelListView):

    resource_name = 'Bills'

    filters = {
        'session': APIFilters.dbfield(help="e.g. 41-1"),
        'introduced': APIFilters.dbfield(filter_types=APIFilters.numeric_filters,
            help="date bill was introduced, e.g. introduced__gt=2010-01-01"),
        'legisinfo_id': APIFilters.dbfield(help="integer ID assigned by parl.gc.ca's LEGISinfo"),
        'number': APIFilters.dbfield('bill__number',
            help="a string, not an integer: e.g. C-10"),
        'law': APIFilters.dbfield('bill__law',
            help="did it become law? True, False"),
        'private_member_bill': APIFilters.dbfield('bill__privatemember',
            help="is it a private member's bill? True, False"),
        'status_code': APIFilters.dbfield('bill__status_code'),
        'sponsor_politician': APIFilters.politician('sponsor_politician'),
        'sponsor_politician_membership': APIFilters.fkey(lambda u: {'sponsor_member': u[-1]}),
    }

    def get_qs(self, request):
        return BillInSession.objects.all().select_related('bill', 'sponsor_politician')

    def get_html(self, request):
        sessions = Session.objects.with_bills()
        len(sessions) # evaluate it
        bills = Bill.objects.filter(sessions=sessions[0])
        votes = VoteQuestion.objects.select_related('bill').filter(session=sessions[0])[:6]

        t = loader.get_template('bills/index.html')
        c = {
            'object_list': bills,
            'session_list': sessions,
            'votes': votes,
            'session': sessions[0],
            'title': 'Bills & Votes',
            'recently_active': Bill.objects.recently_active()
        }

        return HttpResponse(t.render(c, request))
index = BillListView.as_view()


class BillSessionListView(ModelListView):

    def get_json(self, request, session_id):
        return HttpResponseRedirect(urlresolvers.reverse('bills') + '?'
                                    + urlencode({'session': session_id}))

    def get_html(self, request, session_id):
        session = get_object_or_404(Session, pk=session_id)
        bills = Bill.objects.filter(sessions=session)
        votes = VoteQuestion.objects.select_related('bill').filter(session=session)[:6]

        t = loader.get_template('bills/bill_list.html')
        c = {
            'object_list': bills,
            'session': session,
            'votes': votes,
            'title': 'Bills for the %s' % session
        }
        return HttpResponse(t.render(c, request))
bills_for_session = BillSessionListView.as_view()


class VoteListView(ModelListView):

    resource_name = 'Votes'

    api_notes = mark_safe("""<p>What we call votes are <b>divisions</b> in official Parliamentary lingo.
        We refer to an individual person's vote as a <a href="/votes/ballots/">ballot</a>.</p>
    """)

    filters = {
        'session': APIFilters.dbfield(help="e.g. 41-1"),
        'yea_total': APIFilters.dbfield(filter_types=APIFilters.numeric_filters,
            help="# votes for"),
        'nay_total': APIFilters.dbfield(filter_types=APIFilters.numeric_filters,
            help="# votes against, e.g. nay_total__gt=10"),
        'paired_total': APIFilters.dbfield(filter_types=APIFilters.numeric_filters,
            help="paired votes are an odd convention that seem to have stopped in 2011"),
        'date': APIFilters.dbfield(filter_types=APIFilters.numeric_filters,
            help="date__gte=2011-01-01"),
        'number': APIFilters.dbfield(filter_types=APIFilters.numeric_filters,
            help="every vote in a session has a sequential number"),
        'bill': APIFilters.fkey(lambda u: {
            'bill__sessions': u[-2],
            'bill__number': u[-1]
        }, help="e.g. /bills/41-1/C-10/"),
        'result': APIFilters.choices('result', VoteQuestion)
    }

    def get_json(self, request, session_id=None):
        if session_id:
            return HttpResponseRedirect(urlresolvers.reverse('votes') + '?'
                                        + urlencode({'session': session_id}))
        return super(VoteListView, self).get_json(request)

    def get_qs(self, request):
        return VoteQuestion.objects.select_related('bill').order_by('-date', '-number')

    def get_html(self, request, session_id=None):
        if session_id:
            session = get_object_or_404(Session, pk=session_id)
        else:
            session = Session.objects.current()

        t = loader.get_template('bills/votequestion_list.html')
        c = {
            'object_list': self.get_qs(request).filter(session=session),
            'session': session,
            'title': 'Votes for the %s' % session
        }
        return HttpResponse(t.render(c, request))
votes_for_session = VoteListView.as_view()
        
def vote_pk_redirect(request, vote_id):
    vote = get_object_or_404(VoteQuestion, pk=vote_id)
    return HttpResponsePermanentRedirect(
        urlresolvers.reverse('vote', kwargs={
        'session_id': vote.session_id, 'number': vote.number}))


class VoteDetailView(ModelDetailView):

    resource_name = 'Vote'

    api_notes = VoteListView.api_notes

    def get_object(self, request, session_id, number):
        return get_object_or_404(VoteQuestion, session=session_id, number=number)

    def get_related_resources(self, request, obj, result):
        return {
            'ballots_url': urlresolvers.reverse('vote_ballots') + '?' +
                urlencode({'vote': result['url']}),
            'votes_url': urlresolvers.reverse('votes')
        }

    def get_html(self, request, session_id, number):
        vote = self.get_object(request, session_id, number)
        membervotes = MemberVote.objects.filter(votequestion=vote)\
            .order_by('member__party', 'member__politician__name_family')\
            .select_related('member', 'member__party', 'member__politician')
        partyvotes = vote.partyvote_set.select_related('party').all()

        c = {
            'vote': vote,
            'membervotes': membervotes,
            'parties_y': [pv.party for pv in partyvotes if pv.vote == 'Y'],
            'parties_n': [pv.party for pv in partyvotes if pv.vote == 'N']
        }
        t = loader.get_template("bills/votequestion_detail.html")
        return HttpResponse(t.render(c, request))
vote = VoteDetailView.as_view()


class BallotListView(ModelListView):

    resource_name = 'Ballots'

    filters = {
        'vote': APIFilters.fkey(lambda u: {'votequestion__session': u[-2],
                                           'votequestion__number': u[-1]},
                                help="e.g. /votes/41-1/472/"),
        'politician': APIFilters.politician(),
        'politician_membership': APIFilters.fkey(lambda u: {'member': u[-1]},
            help="e.g. /politicians/roles/326/"),
        'ballot': APIFilters.choices('vote', MemberVote),
        'dissent': APIFilters.dbfield('dissent',
            help="does this look like a vote against party line? not reliable for research. True, False")
    }

    def get_qs(self, request):
        return MemberVote.objects.all().select_related(
            'votequestion').order_by('-votequestion__date', '-votequestion__number')

    def object_to_dict(self, obj):
        return obj.to_api_dict(representation='list')
ballots = BallotListView.as_view()

class BillListFeed(Feed):
    title = 'Bills in the House of Commons'
    description = 'New bills introduced to the House, from openparliament.ca.'
    link = "/bills/"
    
    def items(self):
        return Bill.objects.filter(introduced__isnull=False).order_by('-introduced', 'number_only')[:25]
    
    def item_title(self, item):
        return "Bill %s (%s)" % (item.number,
            "Private member's" if item.privatemember else "Government")
    
    def item_description(self, item):
        return item.name
        
    def item_link(self, item):
        return item.get_absolute_url()
        
    
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
