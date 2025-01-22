import datetime
from collections import Counter, defaultdict
import json
import re

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
            return self.get(billinsession__legisinfo_id=legisinfo_id)
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
            if BillInSession.objects.filter(legisinfo_id=int(legisinfo_id)).exists():
                raise Bill.MultipleObjectsReturned(
                    "There's already a bill with LEGISinfo id %s" % legisinfo_id)
        try:
            bill = Bill.objects.get(number=number, sessions=session)
            logger.error("Potential duplicate LEGISinfo ID: %s in %s exists, but trying to create with ID %s" %
                (number, session, legisinfo_id))
            return bill
        except Bill.DoesNotExist:
            bill = self.create(number=number)
            BillInSession.objects.create(bill=bill, session=session,
                    legisinfo_id=legisinfo_id)
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
    number = models.CharField(max_length=10)
    number_only = models.SmallIntegerField()
    institution = models.CharField(max_length=1, db_index=True, choices=CHAMBERS)
    sessions = models.ManyToManyField(Session, through='BillInSession')
    privatemember = models.BooleanField(blank=True, null=True)
    sponsor_member = models.ForeignKey(ElectedMember, blank=True, null=True, on_delete=models.CASCADE)
    sponsor_politician = models.ForeignKey(Politician, blank=True, null=True, on_delete=models.CASCADE)
    law = models.BooleanField(blank=True, null=True)

    status_date = models.DateField(blank=True, null=True, db_index=True)
    status_code = models.CharField(max_length=50, blank=True)

    added = models.DateField(default=datetime.date.today, db_index=True)
    introduced = models.DateField(blank=True, null=True)
    text_docid = models.IntegerField(blank=True, null=True,
        help_text="The parl.gc.ca document ID of the latest version of the bill's text")
    
    objects = BillManager()

    name = language_property('name')
    short_title = language_property('short_title')
   
    class Meta:
        ordering = ('privatemember', 'institution', 'number_only')
    
    def __str__(self):
        return "%s - %s" % (self.number, self.name)
        
    def get_absolute_url(self):
        return self.url_for_session(self.session)

    def url_for_session(self, session):
        return reverse('bill', kwargs={
            'session_id': session.id, 'bill_number': self.number})
        
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
        summary_session = (self.billinsession_set.filter(library_summary_available=True)
                           .order_by('-introduced').values_list('session', flat=True).first())
        if summary_session:
            return f"https://loppublicservices.parl.ca/PublicWebsiteProxy/Publication/GoToLS?billNumber={self.number}&lang={lang}_CA&parlSession={summary_session.replace('-', '')}"

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
        
    def get_session(self):
        """Returns the most recent session this bill belongs to."""
        try:
            self.__dict__['session'] = s = self.sessions.all().order_by('-start')[0]
            return s
        except (IndexError, ValueError):
            return getattr(self, '_session', None)

    def set_temporary_session(self, session):
        """To deal with tricky save logic, saves a session to the object for cases
        when self.sessions.all() won't get exist in the DB."""
        self._session = session

    @memoize_property
    def _get_house_bill_stages_json(self):
        raw_json = self.billinsession_set.order_by('-session').values_list('billstages_json', flat=True)
        r = []
        for rj in raw_json:
            if rj:
                r.extend(json.loads(rj).get('HouseBillStages', []))
        return r

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

    def _get_related_debates_info(self):
        data = self._get_house_bill_stages_json()
        sittings = []
        for stage in data:
            if stage.get('Sittings'):
                for s in stage['Sittings']:
                    sittings.append({
                        'name': s['Name'],
                        'number': s['Number'],
                        'session': "%s-%s" % (stage['ParliamentNumber'], stage['SessionNumber']),
                        'date': s['Date'][:10]
                    })
        return sittings

    def get_second_reading_debate(self):
        """Returns a QuerySet of Statements representing the second-reading debate
        of this bill."""
        second_reading_sittings = [d for d in self._get_related_debates_info()
            if d['name'] == "Debate at second reading"]
        if not second_reading_sittings:
            return Statement.objects.none()
        debate_ids = Document.debates.filter(date__in=[s['date'] for s in second_reading_sittings]
            ).values_list('id', flat=True)
        qs = Statement.objects.filter(document__in=debate_ids)
        if self.short_title_en:
            qs = qs.filter(h2_en=self.short_title_en)
        else:
            speech_headings = self.statement_set.filter(document__in=debate_ids,
                h1_en__in=('Government Orders', "Private Members' Business")).values_list('h2_en', flat=True)
            if not speech_headings:
                return Statement.objects.none()
            h2 = Counter(speech_headings).most_common(1)[0][0]
            qs = qs.filter(h2_en=h2)
        if not qs.exists():
            logger.warning("Bill %s has second reading sittings, but can't get debate statements")            
        return qs
        
    session = property(get_session)

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

class BillInSessionManager(models.Manager):

    def get_by_legisinfo_id(self, legisinfo_id):
        legisinfo_id = int(legisinfo_id)
        try:
            return self.get(legisinfo_id=legisinfo_id)
        except BillInSession.DoesNotExist:
            from parliament.imports import legisinfo
            legisinfo.import_bill_by_id(legisinfo_id)
            return self.get(legisinfo_id=legisinfo_id)


class BillInSession(models.Model):
    """Represents a bill, as introduced in a single session.

    All bills are, technically, introduced only in a single session.
    But, in a decision which ended up being pretty complicated, we combine
    reintroduced bills into a single Bill object. But it's this model
    that maps one-to-one to most IDs used elsewhere.
    """
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE)
    session = models.ForeignKey(Session, on_delete=models.CASCADE)

    legisinfo_id = models.PositiveIntegerField(db_index=True, blank=True, null=True)
    introduced = models.DateField(blank=True, null=True, db_index=True)
    sponsor_politician = models.ForeignKey(Politician, blank=True, null=True, on_delete=models.CASCADE)
    sponsor_member = models.ForeignKey(ElectedMember, blank=True, null=True, on_delete=models.CASCADE)

    billstages_json = models.TextField(blank=True, null=True)
    library_summary_available = models.BooleanField(default=False)

    objects = BillInSessionManager()

    def __str__(self):
        return "%s in session %s" % (self.bill, self.session_id)

    def get_absolute_url(self):
        return self.bill.url_for_session(self.session)

    def get_legisinfo_url(self, lang='en'):
        return LEGISINFO_BILL_ID_URL % {
            'lang': lang,
            'id': self.legisinfo_id
        }

    def to_api_dict(self, representation):
        d = {
            'session': self.session_id,
            'legisinfo_id': self.legisinfo_id,
            'introduced': str(self.introduced) if self.introduced else None,
            'name': {
                'en': self.bill.name_en,
                'fr': self.bill.name_fr
            },
            'number': self.bill.number
        }
        if representation == 'detail':
            d.update(
                short_title={'en': self.bill.short_title_en, 'fr': self.bill.short_title_fr},
                home_chamber=self.bill.get_institution_display(),
                law=self.bill.law,
                sponsor_politician_url=self.sponsor_politician.get_absolute_url() if self.sponsor_politician else None,
                sponsor_politician_membership_url=reverse('politician_membership',
                    kwargs={'member_id': self.sponsor_member_id}) if self.sponsor_member_id else None,
                text_url=self.bill.get_billtext_url(),
                other_session_urls=[self.bill.url_for_session(s)
                    for s in self.bill.sessions.all()
                    if s.id != self.session_id],
                vote_urls=[vq.get_absolute_url() for vq in VoteQuestion.objects.filter(bill=self.bill_id)],
                private_member_bill=self.bill.privatemember,
                legisinfo_url=self.get_legisinfo_url(),
                status_code=self.bill.status_code,
                status={'en': self.bill.status}
            )
        return d


class BillEvent(models.Model):
    bis = models.ForeignKey(BillInSession, on_delete=models.CASCADE)

    date = models.DateField(db_index=True)

    source_id = models.PositiveIntegerField(unique=True, db_index=True)

    institution = models.CharField(max_length=1, choices=Bill.CHAMBERS)

    status_en = models.TextField()
    status_fr = models.TextField(blank=True)

    debate = models.ForeignKey('hansards.Document', blank=True, null=True, on_delete=models.SET_NULL)
    committee_meetings = models.ManyToManyField('committees.CommitteeMeeting', blank=True)

    status = language_property('status')

    def __str__(self):
        return "%s: %s, %s" % (self.status, self.bis.bill.number, self.date)

    @property
    def bill_number(self):
        return self.bis.bill.number


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