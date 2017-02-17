import datetime
from collections import defaultdict
import re

from django.conf import settings
from django.core import urlresolvers
from django.db import models
from django.utils.safestring import mark_safe

from parliament.committees.models import CommitteeMeeting
from parliament.core.models import Session, ElectedMember, Politician, Party
from parliament.core.utils import language_property
from parliament.hansards.models import Document, Statement
from parliament.activity import utils as activity

import logging
logger = logging.getLogger(__name__)

CALLBACK_URL = 'http://www2.parl.gc.ca/HousePublications/GetWebOptionsCallBack.aspx?SourceSystem=PRISM&ResourceType=Document&ResourceID=%d&language=1&DisplayMode=2'
BILL_VOTES_URL = 'http://www2.parl.gc.ca/Housebills/BillVotes.aspx?Language=E&Parl=%s&Ses=%s&Bill=%s'

LEGISINFO_BILL_URL = 'http://www.parl.gc.ca/LegisInfo/BillDetails.aspx?Language=%(lang)s&Mode=1&Bill=%(bill)s&Parl=%(parliament)s&Ses=%(session)s'
LEGISINFO_BILL_ID_URL = 'http://www.parl.gc.ca/LEGISINFO/BillDetails.aspx?Language=%(lang)s&Mode=1&billId=%(id)s'
PARLIAMENT_DOCVIEWER_URL = 'http://parl.gc.ca/HousePublications/Publication.aspx?Language=%(lang)s&Mode=1&DocId=%(docid)s'

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


class Bill(models.Model): 
    CHAMBERS = (
        ('C', 'House'),
        ('S', 'Senate'),
    )
    STATUS_CODES = {
        u'BillNotActive': 'Not active',
        u'WillNotBeProceededWith': 'Dead',
        u'RoyalAssentAwaiting': 'Awaiting royal assent',
        u'BillDefeated': 'Defeated',
        u'HouseAtReportStage': 'Report stage (House)',
        u'RoyalAssentGiven': 'Law (royal assent given)',
        u'SenateAt1stReading': 'First reading (Senate)',
        u'HouseAt1stReading': 'First reading (House)',
        u'HouseAt2ndReading': 'Second reading (House)',
        u'HouseAtReportStageAndSecondReading': 'Report stage and second reading (House)',
        u'SenateAt2ndReading': 'Second reading (Senate)',
        u'SenateAt3rdReading': 'Third reading (Senate)',
        u'HouseAt3rdReading': 'Third reading (House)',
        u'HouseInCommittee': 'In committee (House)',
        u'SenateInCommittee': 'In committee (Senate)',
        u'SenateConsiderationOfCommitteeReport': 'Considering committee report (Senate)',
        u'HouseConsiderationOfCommitteeReport': 'Considering committee report (House)',
        u'SenateConsiderationOfAmendments': 'Considering amendments (Senate)',
        u'HouseConsiderationOfAmendments': 'Considering amendments (House)',
        u'Introduced': 'Introduced'
    }

    name_en = models.TextField(blank=True)
    name_fr = models.TextField(blank=True)
    short_title_en = models.TextField(blank=True)
    short_title_fr = models.TextField(blank=True)
    number = models.CharField(max_length=10)
    number_only = models.SmallIntegerField()
    institution = models.CharField(max_length=1, db_index=True, choices=CHAMBERS)
    sessions = models.ManyToManyField(Session, through='BillInSession')
    privatemember = models.NullBooleanField()
    sponsor_member = models.ForeignKey(ElectedMember, blank=True, null=True)
    sponsor_politician = models.ForeignKey(Politician, blank=True, null=True)
    law = models.NullBooleanField()

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
    
    def __unicode__(self):
        return "%s - %s" % (self.number, self.name)
        
    def get_absolute_url(self):
        return self.url_for_session(self.session)

    def url_for_session(self, session):
        return urlresolvers.reverse('bill', kwargs={
            'session_id': session.id, 'bill_number': self.number})
        
    def get_legisinfo_url(self, lang='E'):
        return LEGISINFO_BILL_URL % {
            'lang': lang,
            'bill': self.number.replace('-', ''),
            'parliament': self.session.parliamentnum,
            'session': self.session.sessnum
        }
        
    legisinfo_url = property(get_legisinfo_url)
        
    def get_billtext_url(self, lang='E', single_page=False):
        if not self.text_docid:
            return None
        url = PARLIAMENT_DOCVIEWER_URL % {
            'lang': lang,
            'docid': self.text_docid
        }
        if single_page:
            url += '&File=4&Col=1'
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

    def get_related_debates(self):
        return Document.objects.filter(billinsession__bill=self)

    def get_committee_meetings(self):
        return CommitteeMeeting.objects.filter(billevent__bis__bill=self)

    def get_major_speeches(self):
        doc_ids = list(self.get_related_debates().values_list('id', flat=True))
        if self.short_title_en:
            qs = Statement.objects.filter(h2_en__iexact=self.short_title_en, wordcount__gt=50)
        else:
            qs = self.statement_set.filter(wordcount__gt=100)
        return qs.filter(document__in=doc_ids, procedural=False)

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
    bill = models.ForeignKey(Bill)
    session = models.ForeignKey(Session)

    legisinfo_id = models.PositiveIntegerField(db_index=True, blank=True, null=True)
    introduced = models.DateField(blank=True, null=True, db_index=True)
    sponsor_politician = models.ForeignKey(Politician, blank=True, null=True)
    sponsor_member = models.ForeignKey(ElectedMember, blank=True, null=True)

    debates = models.ManyToManyField('hansards.Document', through='BillEvent')

    objects = BillInSessionManager()

    def __unicode__(self):
        return u"%s in session %s" % (self.bill, self.session_id)

    def get_absolute_url(self):
        return self.bill.url_for_session(self.session)

    def get_legisinfo_url(self, lang='E'):
        return LEGISINFO_BILL_ID_URL % {
            'lang': lang,
            'id': self.legisinfo_id
        }

    def to_api_dict(self, representation):
        d = {
            'session': self.session_id,
            'legisinfo_id': self.legisinfo_id,
            'introduced': unicode(self.introduced) if self.introduced else None,
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
                sponsor_politician_membership_url=urlresolvers.reverse('politician_membership',
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
    bis = models.ForeignKey(BillInSession)

    date = models.DateField(db_index=True)

    source_id = models.PositiveIntegerField(unique=True, db_index=True)

    institution = models.CharField(max_length=1, choices=Bill.CHAMBERS)

    status_en = models.TextField()
    status_fr = models.TextField(blank=True)

    debate = models.ForeignKey('hansards.Document', blank=True, null=True, on_delete=models.SET_NULL)
    committee_meetings = models.ManyToManyField('committees.CommitteeMeeting', blank=True)

    status = language_property('status')

    def __unicode__(self):
        return u"%s: %s, %s" % (self.status, self.bis.bill.number, self.date)

    @property
    def bill_number(self):
        return self.bis.bill.number


class BillText(models.Model):

    bill = models.ForeignKey(Bill)
    docid = models.PositiveIntegerField(unique=True, db_index=True)

    created = models.DateTimeField(default=datetime.datetime.now)

    text_en = models.TextField()
    text_fr = models.TextField(blank=True)

    text = language_property('text')

    def __unicode__(self):
        return u"Document #%d for %s" % (self.docid, self.bill)

    @property
    def summary(self):
        match = re.search(r'SUMMARY\n([\s\S]+?)(Also a|A)vailable on', self.text_en)
        return match.group(1).strip() if match else None

    @property
    def summary_html(self):
        summary = self.summary
        if not summary:
            return ''
        return mark_safe('<p>' + summary.replace('\n', '</p><p>') + '</p>')

        
VOTE_RESULT_CHOICES = (
    ('Y', 'Passed'), # Agreed to
    ('N', 'Failed'), # Negatived
    ('T', 'Tie'),
)
class VoteQuestion(models.Model):
    
    bill = models.ForeignKey(Bill, blank=True, null=True)
    session = models.ForeignKey(Session)
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
    
    def __unicode__(self):
        return u"Vote #%s on %s" % (self.number, self.date)
        
    class Meta:
        ordering=('-date', '-number')

    def to_api_dict(self, representation):
        r = {
            'bill_url': self.bill.get_absolute_url() if self.bill else None,
            'session': self.session_id,
            'number': self.number,
            'date': unicode(self.date),
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
            votes = sorted(parties[party].items(), key=lambda i: i[1])
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
            
    @models.permalink
    def get_absolute_url(self):
        return ('vote', [],
            {'session_id': self.session_id, 'number': self.number})

VOTE_CHOICES = [
    ('Y', 'Yes'),
    ('N', 'No'),
    ('P', 'Paired'),
    ('A', "Didn't vote"),
]
class MemberVote(models.Model):
    
    votequestion = models.ForeignKey(VoteQuestion)
    member = models.ForeignKey(ElectedMember)
    politician = models.ForeignKey(Politician)
    vote = models.CharField(max_length=1, choices=VOTE_CHOICES)
    dissent = models.BooleanField(default=False, db_index=True)
    
    def __unicode__(self):
        return u'%s voted %s on %s' % (self.politician, self.get_vote_display(), self.votequestion)
            
    def save_activity(self):
        activity.save_activity(self, politician=self.politician, date=self.votequestion.date)

    def to_api_dict(self, representation):
        return {
            'vote_url': self.votequestion.get_absolute_url(),
            'politician_url': self.politician.get_absolute_url(),
            'politician_membership_url': urlresolvers.reverse('politician_membership',
                kwargs={'member_id': self.member_id}) if self.member_id else None,
            'ballot': self.get_vote_display(),
        }

VOTE_CHOICES_PARTY = VOTE_CHOICES + [('F', "Free vote")]            
class PartyVote(models.Model):
    
    votequestion = models.ForeignKey(VoteQuestion)
    party = models.ForeignKey(Party)
    vote = models.CharField(max_length=1, choices=VOTE_CHOICES_PARTY)
    disagreement = models.FloatField(null=True)
    
    class Meta:
        unique_together = ('votequestion', 'party')
    
    def __unicode__(self):
        return u'%s voted %s on %s' % (self.party, self.get_vote_display(), self.votequestion)