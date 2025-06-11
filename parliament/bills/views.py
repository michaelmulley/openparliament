import datetime
import logging
from urllib.parse import urlencode

from django.contrib.syndication.views import Feed
from django.urls import reverse
from django.core.paginator import Paginator, InvalidPage, EmptyPage
from django.db.models import Count, Sum
from django.http import HttpResponse, Http404, HttpResponseRedirect, HttpResponsePermanentRedirect
from django.shortcuts import get_object_or_404
from django.template import loader
from django.template.defaultfilters import date as format_date
from django.utils.safestring import mark_safe
from django.views.decorators.vary import vary_on_headers

from parliament.bills.models import Bill, VoteQuestion, MemberVote
from parliament.core.api import ModelListView, ModelDetailView, APIFilters
from parliament.core.models import Session
from parliament.core.utils import is_ajax
from parliament.hansards.models import Statement, Document
from parliament.summaries.models import Summary

logger = logging.getLogger(__name__)

def bill_pk_redirect(request, bill_id):
    bill = get_object_or_404(Bill, pk=bill_id)
    return HttpResponsePermanentRedirect(bill.get_absolute_url())

class BillDetailView(ModelDetailView):

    resource_name = 'Bill'

    def get_object(self, request, session_id, bill_number):
        return Bill.objects.select_related(
            'sponsor_politician').get(session=session_id, number=bill_number)

    def get_related_resources(self, request, obj, result):
        return {
            'bills_url': reverse('bills')
        }

    def _render_page(self, request, qs, per_page=10):
        paginator = Paginator(qs, per_page)

        try:
            pagenum = int(request.GET.get('page', '1'))
        except ValueError:
            pagenum = 1

        if request.GET.get('speech'):
            try:
                idx = list(qs.values_list('urlcache', flat=True)).index(request.GET['speech'])
                pagenum = int(idx / per_page) + 1
            except ValueError:
                logger.warning("Speech %s not found in BillDetailView", request.GET['speech'])            
        try:
            return paginator.page(pagenum)
        except (EmptyPage, InvalidPage):
            return paginator.page(paginator.num_pages)

    def get_html(self, request, session_id, bill_number):
        bill = get_object_or_404(Bill, session=session_id, number=bill_number)

        mentions = Statement.objects.filter(mentioned_bills=bill, document__document_type=Document.DEBATE).order_by(
            '-time', '-sequence').select_related('member', 'member__politician', 'member__riding', 'member__party')
        
        debate_stages = {
            r['bill_debate_stage']: r['words']
            for r in
            Statement.objects.filter(bill_debated=bill, procedural=False).values('bill_debate_stage').annotate(words=Sum("wordcount"))
            if r['words'] > 150
        }
        meetings = bill.get_committee_meetings()
        has_mentions = mentions.exists()
        has_meetings = meetings.exists()

        tab = request.GET.get('tab', '')
        if tab == 'major-speeches': # keep compatibility with old URLs
            tab = 'stage-2'
        if tab not in ('stage-1', 'stage-2', 'stage-3', 'stage-report', 'mentions', 'meetings'):
            tab = ''            
        if not tab:
            for priority in ('3','2','1'):
                if debate_stages.get(priority):
                    tab = 'stage-' + priority
                    break
            if not tab and has_mentions:
                tab = 'mentions'

        per_page = 500 if request.GET.get('singlepage') else 15

        c = {
            'bill': bill,
            'debate_stages': debate_stages,
            'has_mentions': has_mentions,
            'has_meetings': has_meetings,
            'committee_meetings': meetings,
            'votequestions': bill.votequestion_set.all().order_by('-date', '-number'),
            'allow_single_page': True,
            'tab': tab,
            'title': ('Bill %s' % bill.number) + (' (Historical)' if bill.session.end else ''),
            'statements_full_date': True,
            'statements_context_link': tab == 'mentions',
            'similar_bills': bill.similar_bills.all().order_by('-session_id', '-introduced')[:8],
            'same_number_bills': Bill.objects.filter(number=bill.number).exclude(id=bill.id).order_by('-session_id')[:4],
        }

        if tab == 'mentions':
            c['page'] = self._render_page(request, mentions, per_page=per_page)
        elif tab.startswith('stage-'):
            stage_code = tab.split('-')[1]
            if debate_stages.get(stage_code):
                qs = bill.get_debate_at_stage(stage_code)
                reading_speeches = qs.select_related(
                    'member', 'member__politician', 'member__riding', 'member__party')            
                c['page'] = self._render_page(request, reading_speeches, per_page=per_page)
                if stage_code in ('2', '3', 'report'):
                    try:
                        c['reading_summary'] = Summary.objects.get(
                            summary_type='stage_' + stage_code,
                            identifier=bill.get_absolute_url())
                    except Summary.DoesNotExist:
                        pass

        if is_ajax(request):
            if tab == 'meetings':
                t = loader.get_template("bills/related_meetings.inc")
            else:
                t = loader.get_template("bills/reading_debate.inc")
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
        'legisinfo_id': APIFilters.dbfield(help="integer ID assigned by Parliament's LEGISinfo"),
        'number': APIFilters.dbfield('number',
            help="a string, not an integer: e.g. C-10"),
        'law': APIFilters.dbfield('law',
            help="did it become law? True, False"),
        'private_member_bill': APIFilters.dbfield('privatemember',
            help="is it a private member's bill? True, False"),
        'status_code': APIFilters.dbfield('status_code'),
        'sponsor_politician': APIFilters.politician('sponsor_politician'),
        'sponsor_politician_membership': APIFilters.fkey(lambda u: {'sponsor_member': u[-1]}),
    }

    def get_qs(self, request):
        return Bill.objects.all().select_related('sponsor_politician')

    def get_html(self, request):
        sessions = Session.objects.with_bills()
        len(sessions) # evaluate it
        bills = Bill.objects.filter(session=sessions[0]).select_related('sponsor_member', 'sponsor_member__party')
        votes = VoteQuestion.objects.select_related('bill').filter(session=sessions[0])[:6]
        recently_debated = bills.filter(latest_debate_date__isnull=False).order_by('-latest_debate_date')[:12]

        t = loader.get_template('bills/index.html')
        c = {
            'object_list': bills,
            'session_list': sessions,
            'votes': votes,
            'session': sessions[0],
            'title': 'Bills & Votes',
            'recently_debated': recently_debated,
        }

        return HttpResponse(t.render(c, request))
index = BillListView.as_view()


class BillSessionListView(ModelListView):

    def get_json(self, request, session_id):
        return HttpResponseRedirect(reverse('bills') + '?'
                                    + urlencode({'session': session_id}))

    def get_html(self, request, session_id):
        session = get_object_or_404(Session, pk=session_id)
        bills = Bill.objects.filter(session=session)
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
            'bill__session': u[-2],
            'bill__number': u[-1]
        }, help="e.g. /bills/41-1/C-10/"),
        'result': APIFilters.choices('result', VoteQuestion)
    }

    def get_json(self, request, session_id=None):
        if session_id:
            return HttpResponseRedirect(reverse('votes') + '?'
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
        reverse('vote', kwargs={
        'session_id': vote.session_id, 'number': vote.number}))


class VoteDetailView(ModelDetailView):

    resource_name = 'Vote'

    api_notes = VoteListView.api_notes

    def get_object(self, request, session_id, number):
        return get_object_or_404(VoteQuestion, session=session_id, number=number)

    def get_related_resources(self, request, obj, result):
        return {
            'ballots_url': reverse('vote_ballots') + '?' +
                urlencode({'vote': result['url']}),
            'votes_url': reverse('votes')
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
    
    def item_pubdate(self, item):
        return datetime.datetime(item.introduced.year, item.introduced.month, item.introduced.day, 12)
        
    
class BillFeed(Feed):

    def get_object(self, request, bill_id=None, session_id=None, bill_number=None):
        if bill_id:
            return get_object_or_404(Bill, pk=bill_id)
        else:
            return get_object_or_404(Bill, session=session_id, number=bill_number)

    def title(self, bill):
        return "Bill %s" % bill.number

    def link(self, bill):
        return "http://openparliament.ca" + bill.get_absolute_url()

    def description(self, bill):
        return "From openparliament.ca, speeches about Bill %s, %s" % (bill.number, bill.name)

    def items(self, bill):
        statements = Statement.objects.filter(document__document_type=Document.DEBATE,
            bill_debated=bill).order_by('-time', '-sequence').select_related('member', 'member__politician', 'member__riding', 'member__party')[:10]
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
