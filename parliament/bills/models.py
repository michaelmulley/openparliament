import datetime
from collections import Counter, defaultdict
import json
import re
from typing import Literal

from django.conf import settings
from django.urls import reverse
from django.db import models
from django.utils.safestring import mark_safe

from parliament.committees.models import Committee, CommitteeMeeting
from parliament.core.models import Session, ElectedMember, Politician, Party
from parliament.core.utils import language_property, memoize_property
from parliament.hansards.models import Document, Statement
from parliament.activity import utils as activity
from parliament.search.index import register_search_model

import logging
logger = logging.getLogger(__name__)

LEGISINFO_BILL_URL = 'https://www.parl.ca/legisinfo/%(lang)s/bill/%(parliament)s-%(session)s/%(bill)s'
LEGISINFO_BILL_ID_URL = 'https://www.parl.ca/legisinfo/%(lang)s/bill/%(id)s'
PARLIAMENT_DOCVIEWER_URL = 'https://www.parl.ca/DocumentViewer/%(lang)s/%(docid)s'
class BillManager(models.Manager):

    def get_by_legisinfo_id(self, legisinfo_id):
        """Given a House of Commons ID (e.g. from LEGISinfo, or a Hansard link),
        return a Bill, creating it if necessary."""
        legisinfo_id = int(legisinfo_id)
        try:
            return self.get(legisinfo_id=legisinfo_id)
        except Bill.DoesNotExist:
            from parliament.imports import legisinfo
            return legisinfo.import_bill_by_id(legisinfo_id)

    def create_temporary_bill(self, number, session, legisinfo_id=None):
        """Creates a bare-bones Bill object, to be filled in later.

        Used because often it'll be a day or two between when a bill ID is
        first referenced in Hansard and when it shows up in LEGISinfo.
        """
        if legisinfo_id:
            legisinfo_id = int(legisinfo_id)
            if Bill.objects.filter(legisinfo_id=legisinfo_id).exists():
                raise Bill.MultipleObjectsReturned(
                    "There's already a bill with LEGISinfo id %s" % legisinfo_id)
        try:
            bill = Bill.objects.get(number=number, session=session)
            logger.error("Potential duplicate LEGISinfo ID: %s in %s exists, but trying to create with ID %s" %
                (number, session, legisinfo_id))
            return bill
        except Bill.DoesNotExist:
            bill = self.create(number=number, session=session, legisinfo_id=legisinfo_id)
            return bill

    def recently_active(self, number=12):
        return Bill.objects.filter(status_date__isnull=False).exclude(models.Q(privatemember=True) 
            & models.Q(status_code='Introduced')).order_by('-status_date')[:number]


@register_search_model
class Bill(models.Model): 
    CHAMBERS = (
        ('C', 'House'),
        ('S', 'Senate'),
    )
    STATUS_CODES = {
        'BillNotActive': 'Not active',
        'WillNotBeProceededWith': 'Dead',
        'RoyalAssentAwaiting': 'Awaiting royal assent',
        'BillDefeated': 'Defeated',
        'HouseAtReportStage': 'Report stage (House)',
        'SenateAtReportStage': 'Report stage (Senate)',
        'RoyalAssentGiven': 'Law (royal assent given)',
        'SenateAt1stReading': 'First reading (Senate)',
        'HouseAt1stReading': 'First reading (House)',
        'HouseAtReferralToCommitteeBeforeSecondReading': 'Referral to committee before 2nd reading (House)',
        'HouseAt2ndReading': 'Second reading (House)',
        'HouseAtReportStageAndSecondReading': 'Report stage and second reading (House)',
        'SenateAt2ndReading': 'Second reading (Senate)',
        'SenateAt3rdReading': 'Third reading (Senate)',
        'HouseAt3rdReading': 'Third reading (House)',
        'HouseInCommittee': 'In committee (House)',
        'SenateInCommittee': 'In committee (Senate)',
        'SenateConsiderationOfCommitteeReport': 'Considering committee report (Senate)',
        'HouseConsiderationOfCommitteeReport': 'Considering committee report (House)',
        'SenateConsiderationOfAmendments': 'Considering amendments (Senate)',
        'HouseConsiderationOfAmendments': 'Considering amendments (House)',
        'Introduced': 'Introduced',
        'ProForma': 'Not a real bill (bills C-1 and S-1 are weird procedural relics)',
        'SenateBillWaitingHouse': 'Senate bill, now waiting to be considered in the House',
        'HouseBillWaitingSenate': 'Bill passed the House, now waiting to be considered in the Senate',
        'OutsideOrderPrecedence': "Outside the Order of Precedence (a private member's bill that hasn't yet won the draw that determines which private member's bills can be debated)",
        'SenConsideringHouseAmendments': 'At consideration in the Senate of amendments made by the House of Commons',
        'HouseConsideringSenAmendments': 'At consideration in the House of Commons of amendments made by the Senate',
    }

    STATUS_STRING_TO_STATUS_CODE = {
        'At consideration in committee in the House of Commons': 'HouseInCommittee',
        'At consideration in committee in the Senate': 'SenateInCommittee',
        'At second reading in the House of Commons': 'HouseAt2ndReading',
        'At second reading in the Senate': 'SenateAt2ndReading',
        'At third reading in the Senate': 'SenateAt3rdReading',
        'At third reading in the House of Commons': 'HouseAt3rdReading',
        'Bill not proceeded with': 'WillNotBeProceededWith',
        'Introduced as pro forma bill': 'ProForma',
        'Outside the Order of Precedence': 'OutsideOrderPrecedence',
        'Royal assent received': 'RoyalAssentGiven',
        'Senate bill awaiting first reading in the House of Commons': 'SenateBillWaitingHouse',
        'At report stage in the House of Commons': 'HouseAtReportStage',
        'At report stage in the Senate': 'SenateAtReportStage',
        'House of Commons bill awaiting first reading in the Senate': 'HouseBillWaitingSenate',
        'Bill defeated': 'BillDefeated',
        'Awaiting royal assent': 'RoyalAssentAwaiting',
        'At consideration in the Senate of amendments made by the House of Commons': 'SenConsideringHouseAmendments',
        'At consideration in the House of Commons of amendments made by the Senate': 'HouseConsideringSenAmendments',
    }

    name_en = models.TextField(blank=True)
    name_fr = models.TextField(blank=True)
    short_title_en = models.TextField(blank=True)
    short_title_fr = models.TextField(blank=True)
    number = models.CharField(max_length=10, db_index=True)
    number_only = models.SmallIntegerField()
    institution = models.CharField(max_length=1, db_index=True, choices=CHAMBERS)
    session = models.ForeignKey(Session, on_delete=models.PROTECT)
    privatemember = models.BooleanField(blank=True, null=True)
    sponsor_member = models.ForeignKey(ElectedMember, blank=True, null=True, on_delete=models.SET_NULL)
    sponsor_politician = models.ForeignKey(Politician, blank=True, null=True, on_delete=models.SET_NULL)
    law = models.BooleanField(blank=True, null=True)

    status_date = models.DateField(blank=True, null=True, db_index=True)
    status_code = models.CharField(max_length=50, blank=True)

    # The date of the latest major debate on this bill (2nd/3rd/report). This is set
    # when importing Hansard and is intended only for a recently-debated-bills list;
    # it shouldn't be considered complete or authoritative.
    latest_debate_date = models.DateField(blank=True, null=True, db_index=True)

    added = models.DateField(default=datetime.date.today, db_index=True)
    introduced = models.DateField(blank=True, null=True)
    text_docid = models.IntegerField(blank=True, null=True,
        help_text="The parl.gc.ca document ID of the latest version of the bill's text")
    
    legisinfo_id = models.PositiveIntegerField(db_index=True, blank=True, null=True)

    billstages_json = models.TextField(blank=True, null=True) # a raw chunk of the LEGISinfo JSON
    library_summary_available = models.BooleanField(default=False)

    similar_bills = models.ManyToManyField("self", blank=True)
    
    objects = BillManager()

    name = language_property('name')
    short_title = language_property('short_title')
   
    class Meta:
        ordering = ('privatemember', 'institution', 'number_only')
    
    def __str__(self):
        return "%s - %s" % (self.number, self.name)
        
    def get_absolute_url(self):
        return reverse('bill', kwargs={
            'session_id': self.session_id, 'bill_number': self.number})
        
    def get_legisinfo_url(self, lang='en'):
        return LEGISINFO_BILL_URL % {
            'lang': lang,
            'bill': self.number,
            'parliament': self.session.parliamentnum,
            'session': self.session.sessnum
        }
        
    legisinfo_url = property(get_legisinfo_url)
        
    def get_billtext_url(self, lang='en'): 
        if not self.text_docid:
            return None
        url = PARLIAMENT_DOCVIEWER_URL % {
            'lang': lang,
            'docid': self.text_docid
        }
        return url

    def get_text_object(self):
        if not self.text_docid:
            raise BillText.DoesNotExist
        return BillText.objects.get(bill=self, docid=self.text_docid)

    def get_text(self, language=settings.LANGUAGE_CODE):
        try:
            return getattr(self.get_text_object(), 'text_' + language)
        except BillText.DoesNotExist:
            return ''

    def get_summary(self):
        try:
            return self.get_text_object().summary_html
        except BillText.DoesNotExist:
            return ''
        
    def get_library_summary_url(self, lang=settings.LANGUAGE_CODE) -> str | None:
        if not self.library_summary_available:
            return None
        return f"https://loppublicservices.parl.ca/PublicWebsiteProxy/Publication/GoToLS?billNumber={self.number}&lang={lang}_CA&parlSession={self.session_id.replace('-', '')}"

    @property
    def latest_date(self):
        return self.status_date if self.status_date else self.introduced
        
    def save(self, *args, **kwargs):
        if not self.number_only:
            self.number_only = int(re.sub(r'\D', '', self.number))
        if getattr(self, 'privatemember', None) is None:
            self.privatemember = bool(self.number_only >= 200)
        if not self.institution:
            self.institution = self.number[0]
        if not self.law and self.status_code == 'RoyalAssentGiven':
            self.law = True
        super(Bill, self).save(*args, **kwargs)

    def save_sponsor_activity(self):
        if self.sponsor_politician:
            activity.save_activity(
                obj=self,
                politician=self.sponsor_politician,
                date=self.introduced if self.introduced else (self.added - datetime.timedelta(days=1)),
                variety='billsponsor',
            )

    @memoize_property
    def _get_house_bill_stages_json(self) -> list:
        if not self.billstages_json:
            return []
        return json.loads(self.billstages_json).get('HouseBillStages', [])

    def get_committee_meetings(self):
        """Return a QuerySet of CommitteeMeetings where this bill was considered."""
        data = self._get_house_bill_stages_json()
        for stage in data:
            if stage.get('CommitteeMeetings'):
                acronym = stage['CommitteeMeetings'][0]['CommitteeAcronym']
                numbers = [int(s['Number']) for s in stage['CommitteeMeetings']
                    if s['CommitteeAcronym'] == acronym]
                session = "%s-%s" % (stage['ParliamentNumber'], stage['SessionNumber'])
                cmte = Committee.objects.get_by_acronym(acronym, session)
                return CommitteeMeeting.objects.filter(committee=cmte, 
                    session=session, number__in=numbers)
        return CommitteeMeeting.objects.none()
    
    def get_debate_at_stage(self, stage: Literal['1','2','3','report']) -> models.QuerySet[Statement]:
        return Statement.objects.filter(bill_debated=self, bill_debate_stage=stage).order_by(
            '-document__session', 'document__date', 'sequence')

    @property
    def status(self):
        return self.STATUS_CODES.get(self.status_code, 'Unknown')

    @property
    def dead(self):
        return self.status_code in ('BillNotActive', 'WillNotBeProceededWith', 'BillDefeated')

    @property
    def dormant(self):
        return (self.status_date and (datetime.date.today() - self.status_date).days > 150)
    
    def search_dict(self):
        d = {
            'text': self.get_text(),
            'title': self.name,
            'number': self.number,
            'url': self.get_absolute_url(),
            'session': str(self.session),
            'doctype': 'bill'
        }
        if self.introduced:
            d['date'] = self.introduced.isoformat() + 'T12:00:00Z'
        if self.sponsor_politician:
            d['politician'] = self.sponsor_politician.name
            d['politician_id'] = self.sponsor_politician.identifier
        if self.sponsor_member:
            d['party'] = self.sponsor_member.party.short_name
        d['searchtext'] = f"{self.name} {self.short_title_en} {d['text']}"
        d['boosted'] = f"Bill {self.number}"
        if len(d['title']) >= 150:
            d['title'] = self.short_title if self.short_title else (self.name[:140] + '…')
        return d
    
    def search_should_index(self):
        return True # index all bills
    
    @classmethod
    def search_get_qs(cls):
        return Bill.objects.all().prefetch_related(
            'sponsor_politician', 'sponsor_member', 'sponsor_member__party'
        )
    
    def to_api_dict(self, representation):
        d = {
            'session': self.session_id,
            'legisinfo_id': self.legisinfo_id,
            'introduced': str(self.introduced) if self.introduced else None,
            'name': {
                'en': self.name_en,
                'fr': self.name_fr
            },
            'number': self.number
        }
        if representation == 'detail':
            d.update(
                short_title={'en': self.short_title_en, 'fr': self.short_title_fr},
                home_chamber=self.get_institution_display(),
                law=self.law,
                sponsor_politician_url=self.sponsor_politician.get_absolute_url() if self.sponsor_politician else None,
                sponsor_politician_membership_url=reverse('politician_membership',
                    kwargs={'member_id': self.sponsor_member_id}) if self.sponsor_member_id else None,
                text_url=self.get_billtext_url(),
                # other_session_urls=[self.bill.url_for_session(s)
                #     for s in self.bill.sessions.all()
                #     if s.id != self.session_id],
                vote_urls=[vq.get_absolute_url() for vq in VoteQuestion.objects.filter(bill=self)],
                private_member_bill=self.privatemember,
                legisinfo_url=self.get_legisinfo_url(),
                status_code=self.status_code,
                status={'en': self.status}
            )
        return d    

class BillText(models.Model):

    bill = models.ForeignKey(Bill, on_delete=models.CASCADE)
    docid = models.PositiveIntegerField(unique=True, db_index=True)

    created = models.DateTimeField(default=datetime.datetime.now)

    text_en = models.TextField()
    text_fr = models.TextField(blank=True)
    summary_en = models.TextField(blank=True)

    text = language_property('text')

    def __str__(self):
        return "Document #%d for %s" % (self.docid, self.bill)

    @property
    def summary_html(self):
        summary = self.summary_en
        if not summary:
            return ''
        return mark_safe('<p>' + summary.replace('\n', '<br>') + '</p>')

        
VOTE_RESULT_CHOICES = (
    ('Y', 'Passed'), # Agreed to
    ('N', 'Failed'), # Negatived
    ('T', 'Tie'),
)
class VoteQuestion(models.Model):
    
    bill = models.ForeignKey(Bill, blank=True, null=True, on_delete=models.CASCADE)
    session = models.ForeignKey(Session, on_delete=models.CASCADE)
    number = models.PositiveIntegerField()
    date = models.DateField(db_index=True)
    description_en = models.TextField()
    description_fr = models.TextField(blank=True)
    result = models.CharField(max_length=1, choices=VOTE_RESULT_CHOICES)
    yea_total = models.SmallIntegerField()
    nay_total = models.SmallIntegerField()
    paired_total = models.SmallIntegerField()
    context_statement = models.ForeignKey('hansards.Statement',
        blank=True, null=True, on_delete=models.SET_NULL)

    description = language_property('description')
    
    def __str__(self):
        return "Vote #%s on %s" % (self.number, self.date)
        
    class Meta:
        ordering=('-date', '-number')

    def to_api_dict(self, representation):
        r = {
            'bill_url': self.bill.get_absolute_url() if self.bill else None,
            'session': self.session_id,
            'number': self.number,
            'date': str(self.date),
            'description': {'en': self.description_en, 'fr': self.description_fr},
            'result': self.get_result_display(),
            'yea_total': self.yea_total,
            'nay_total': self.nay_total,
            'paired_total': self.paired_total,
        }
        if representation == 'detail':
            r.update(
                context_statement=self.context_statement.get_absolute_url() if self.context_statement else None,
                party_votes=[{
                    'vote': pv.get_vote_display(),
                    'disagreement': pv.disagreement,
                    'party': {
                        'name': {'en': pv.party.name},
                        'short_name': {'en': pv.party.short_name}
                    },
                } for pv in self.partyvote_set.all()]
            )
        return r

    def label_absent_members(self):
        for member in ElectedMember.objects.on_date(self.date).exclude(membervote__votequestion=self):
            MemberVote(votequestion=self, member=member, politician_id=member.politician_id, vote='A').save()
            
    def label_party_votes(self):
        """Create PartyVote objects representing the party-line vote; label individual dissenting votes."""
        membervotes = self.membervote_set.select_related('member', 'member__party').all()
        parties = defaultdict(lambda: defaultdict(int))
        
        for mv in membervotes:
            if mv.member.party.name != 'Independent':
                parties[mv.member.party][mv.vote] += 1
        
        partyvotes = {}
        for party in parties:
            # Find the most common vote
            votes = sorted(list(parties[party].items()), key=lambda i: i[1])
            partyvotes[party] = votes[-1][0]
            
            # Find how many people voted with the majority
            yn = (parties[party]['Y'], parties[party]['N'])
            try:
                disagreement = float(min(yn))/sum(yn)
            except ZeroDivisionError:
                disagreement = 0.0
                
            # If more than 15% of the party voted against the party majority,
            # label this as a free vote.
            if disagreement >= 0.15:
                partyvotes[party] = 'F'
            
            PartyVote.objects.filter(party=party, votequestion=self).delete()
            PartyVote.objects.create(party=party, votequestion=self, vote=partyvotes[party], disagreement=disagreement)
        
        for mv in membervotes:
            if mv.member.party.name != 'Independent' \
              and mv.vote != partyvotes[mv.member.party] \
              and mv.vote in ('Y', 'N') \
              and partyvotes[mv.member.party] in ('Y', 'N'):
                mv.dissent = True
                mv.save()
            
    def get_absolute_url(self):
        return reverse('vote', kwargs={
            'session_id': self.session_id, 'number': self.number})

VOTE_CHOICES = [
    ('Y', 'Yes'),
    ('N', 'No'),
    ('P', 'Paired'),
    ('A', "Didn't vote"),
]
class MemberVote(models.Model):
    
    votequestion = models.ForeignKey(VoteQuestion, on_delete=models.CASCADE)
    member = models.ForeignKey(ElectedMember, on_delete=models.CASCADE)
    politician = models.ForeignKey(Politician, on_delete=models.CASCADE)
    vote = models.CharField(max_length=1, choices=VOTE_CHOICES)
    dissent = models.BooleanField(default=False, db_index=True)
    
    def __str__(self):
        return '%s voted %s on %s' % (self.politician, self.get_vote_display(), self.votequestion)
            
    def save_activity(self):
        activity.save_activity(self, politician=self.politician, date=self.votequestion.date)

    def to_api_dict(self, representation):
        return {
            'vote_url': self.votequestion.get_absolute_url(),
            'politician_url': self.politician.get_absolute_url(),
            'politician_membership_url': reverse('politician_membership',
                kwargs={'member_id': self.member_id}) if self.member_id else None,
            'ballot': self.get_vote_display(),
        }

VOTE_CHOICES_PARTY = VOTE_CHOICES + [('F', "Free vote")]            
class PartyVote(models.Model):
    
    votequestion = models.ForeignKey(VoteQuestion, on_delete=models.CASCADE)
    party = models.ForeignKey(Party, on_delete=models.CASCADE)
    vote = models.CharField(max_length=1, choices=VOTE_CHOICES_PARTY)
    disagreement = models.FloatField(null=True)
    
    class Meta:
        unique_together = ('votequestion', 'party')
    
    def __str__(self):
        return '%s voted %s on %s' % (self.party, self.get_vote_display(), self.votequestion)