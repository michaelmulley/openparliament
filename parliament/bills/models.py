import urllib, urllib2, re
import datetime
from collections import defaultdict

from django.db import models
from BeautifulSoup import BeautifulSoup

from parliament.core.models import Session, InternalXref, ElectedMember, Politician, Party
from parliament.activity import utils as activity
from parliament.core.utils import memoize_property


CALLBACK_URL = 'http://www2.parl.gc.ca/HousePublications/GetWebOptionsCallBack.aspx?SourceSystem=PRISM&ResourceType=Document&ResourceID=%d&language=1&DisplayMode=2'
BILL_VOTES_URL = 'http://www2.parl.gc.ca/Housebills/BillVotes.aspx?Language=E&Parl=%s&Ses=%s&Bill=%s'

LEGISINFO_BILL_URL = 'http://www.parl.gc.ca/LegisInfo/BillDetails.aspx?Language=%(lang)s&Mode=1&Bill=%(bill)s&Parl=%(parliament)s&Ses=%(session)s'
PARLIAMENT_DOCVIEWER_URL = 'http://parl.gc.ca/HousePublications/Publication.aspx?Language=%(lang)s&Mode=1&DocId=%(docid)s'

class BillManager(models.Manager):
    
    def get_by_callback_id(self, callback):
        """Given a callback ID from a link on a Hansard page, return a Bill."""
        try:
            xref = InternalXref.objects.get(schema='bill_callbackid', int_value=callback)
            if xref.target_id < 0:
                raise Bill.DoesNotExist("Stored as invalid callback")
            return self.get_query_set().get(pk=xref.target_id)
        except InternalXref.DoesNotExist:
            pass
            
        callpage = urllib2.urlopen(CALLBACK_URL % callback)
        
        match = re.search(r'Parl=(\d+)&Ses=(\d)(?:&Bill=|#)([CS][0-9]+[A-Z]?)', callpage.read())
        if not match:
            print "Couldn't find parseable link in get_by_callback_id"
            raise Bill.DoesNotExist()
        (parliamentnum, sessnum, billnum) = match.groups()
        billnum = billnum[0] + '-' + billnum[1:] # we use the C-52 style, not C52\
        session = Session.objects.get(parliamentnum=parliamentnum, sessnum=sessnum)
        try:
            bill = self.get_query_set().get(number=billnum, sessions=session)
        except Bill.DoesNotExist:
            # Let's see if we can get the bill name
            billname = ''
            if billnum[0] == 'C':
                try:
                    votespage = urllib2.urlopen(BILL_VOTES_URL %
                        (parliamentnum, sessnum, billnum.replace('-', '')))
                    votesoup = BeautifulSoup(votespage.read())
                    votediv = votesoup.find('div', 'VotesBill')
                    billname = votediv.string.strip()
                except Exception as e:
                    print e # FIXME logging
            
            bill = Bill(name=billname, number=billnum, institution=billnum[0])
            bill.session = session
            bill.save()
        
        InternalXref(schema='bill_callbackid', int_value=callback, target_id=bill.id).save()
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
    sessions = models.ManyToManyField(Session)
    privatemember = models.NullBooleanField()
    sponsor_member = models.ForeignKey(ElectedMember, blank=True, null=True)
    sponsor_politician= models.ForeignKey(Politician, blank=True, null=True)
    law = models.NullBooleanField()
    status = models.CharField(max_length=200, blank=True)
    status_fr = models.CharField(max_length=200, blank=True)
    status_date = models.DateField(blank=True, null=True)
    added = models.DateField(default=datetime.date.today, db_index=True)
    introduced = models.DateField(blank=True, null=True)
    text_docid = models.IntegerField(blank=True, null=True,
        help_text="The parl.gc.ca document ID of the latest version of the bill's text")
    
    objects = BillManager()
    
    class Meta:
        ordering = ('privatemember', 'institution', 'number_only')
    
    def __unicode__(self):
        return "%s - %s" % (self.number, self.name)
        
    @models.permalink
    def get_absolute_url(self):
        return ('parliament.bills.views.bill_pk_redirect', [self.id])
        
    def get_legisinfo_url(self, lang='E'):
        return LEGISINFO_BILL_URL % {
            'lang': lang,
            'bill': self.number.replace('-', ''),
            'parliament': self.session.parliamentnum,
            'session': self.session.sessnum
        }
        
    legisinfo_url = property(get_legisinfo_url)
        
    def get_billtext_url(self, lang='E'):
        if not self.text_docid:
            return None
        return PARLIAMENT_DOCVIEWER_URL % {
            'lang': lang,
            'docid': self.text_docid
        }
        
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
        if getattr(self, '_save_session', None):
            self.sessions.add(self._save_session)

    def save_sponsor_activity(self):
        if self.sponsor_politician:
            activity.save_activity(
                obj=self,
                politician=self.sponsor_politician,
                date=self.introduced if self.introduced else (self.added - datetime.timedelta(days=1)),
                variety='billsponsor',
            )
        
    @memoize_property
    def get_session(self):
        """Returns the most recent session this bill belongs to."""
        try:
            return self.sessions.all().order_by('-start')[0]
        except (IndexError, ValueError):
            return getattr(self, '_save_session', None)
            
    def set_session(self, session):
        self._save_session = session
        
    session = property(get_session, set_session)
        
VOTE_RESULT_CHOICES = (
    ('Y', 'Passed'), # Agreed to
    ('N', 'Failed'), # Negatives
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