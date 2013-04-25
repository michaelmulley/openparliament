import datetime
from collections import defaultdict
import re

from django.conf import settings
from django.core import urlresolvers
from django.db import models

from parliament.core.models import Session, InternalXref, ElectedMember, Politician, Party
from parliament.activity import utils as activity
from parliament.core.utils import memoize_property

import logging
logger = logging.getLogger(__name__)

CALLBACK_URL = 'http://www2.parl.gc.ca/HousePublications/GetWebOptionsCallBack.aspx?SourceSystem=PRISM&ResourceType=Document&ResourceID=%d&language=1&DisplayMode=2'
BILL_VOTES_URL = 'http://www2.parl.gc.ca/Housebills/BillVotes.aspx?Language=E&Parl=%s&Ses=%s&Bill=%s'

LEGISINFO_BILL_URL = 'http://www.parl.gc.ca/LegisInfo/BillDetails.aspx?Language=%(lang)s&Mode=1&Bill=%(bill)s&Parl=%(parliament)s&Ses=%(session)s'
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

class Bill(models.Model):
    
    name = models.TextField(blank=True)
    name_fr = models.TextField(blank=True)
    short_title_en = models.TextField(blank=True)
    short_title_fr = models.TextField(blank=True)
    number = models.CharField(max_length=10)
    number_only = models.SmallIntegerField()
    institution = models.CharField(max_length=1, db_index=True, choices=(
        ('C', 'House'),
        ('S', 'Senate'),
    ))
    sessions = models.ManyToManyField(Session, through='BillInSession')
    privatemember = models.NullBooleanField()
    sponsor_member = models.ForeignKey(ElectedMember, blank=True, null=True)
    sponsor_politician= models.ForeignKey(Politician, blank=True, null=True)
    law = models.NullBooleanField()

    # TODO: Remodel status to allow multiple status events, with dates
    status = models.CharField(max_length=200, blank=True)
    status_fr = models.CharField(max_length=200, blank=True)
    status_date = models.DateField(blank=True, null=True)
    added = models.DateField(default=datetime.date.today, db_index=True)
    introduced = models.DateField(blank=True, null=True)
    text_docid = models.IntegerField(blank=True, null=True,
        help_text="The parl.gc.ca document ID of the latest version of the bill's text")

    display = models.BooleanField('Display on site?', db_index=True, default=True)

    objects = BillManager()
    
    class Meta:
        ordering = ('privatemember', 'institution', 'number_only')
    
    def __unicode__(self):
        return "%s - %s" % (self.number, self.name)
        
    def get_absolute_url(self):
        return self.url_for_session(self.session)

    def url_for_session(self, session):
        return urlresolvers.reverse('parliament.bills.views.bill', kwargs={
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

    def get_text(self, language=settings.LANGUAGE_CODE):
        if not self.text_docid:
            return ''
        try:
            bt = BillText.objects.get(bill=self, docid=self.text_docid)
            return getattr(bt, 'text_' + language)
        except BillText.DoesNotExist:
            return ''

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
        if not self.law and 'Royal Assent' in self.status:
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
    introduced = models.DateField(blank=True, null=True)
    sponsor_politician = models.ForeignKey(Politician, blank=True, null=True)
    sponsor_member = models.ForeignKey(ElectedMember, blank=True, null=True)

    objects = BillInSessionManager()

    def __unicode__(self):
        return u"%s in session %s" % (self.bill, self.session_id)

    def get_absolute_url(self):
        return self.bill.url_for_session(self.session)

class BillText(models.Model):

    bill = models.ForeignKey(Bill)
    docid = models.PositiveIntegerField(unique=True, db_index=True)

    created = models.DateTimeField(default=datetime.datetime.now)

    text_en = models.TextField()
    text_fr = models.TextField(blank=True)

    def __unicode__(self):
        return u"Document #%d for %s" % (self.docid, self.bill)

        
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
    description = models.TextField()
    result = models.CharField(max_length=1, choices=VOTE_RESULT_CHOICES)
    yea_total = models.SmallIntegerField()
    nay_total = models.SmallIntegerField()
    paired_total = models.SmallIntegerField()
    context_statement = models.ForeignKey('hansards.Statement',
        blank=True, null=True, on_delete=models.SET_NULL)
    
    def __unicode__(self):
        return u"Vote #%s on %s" % (self.number, self.date)
        
    class Meta:
        ordering=('-date', '-number')

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
        return ('parliament.bills.views.vote', [],
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
