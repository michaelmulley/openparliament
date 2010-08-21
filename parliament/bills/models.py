import urllib, urllib2, re
import datetime
from collections import defaultdict

from django.db import models
from BeautifulSoup import BeautifulSoup

from parliament.core.models import Session, InternalXref, ElectedMember, Politician, Party
from parliament.activity import utils as activity
from parliament.core.utils import memoize, memoize_property


CALLBACK_URL = 'http://www2.parl.gc.ca/HousePublications/GetWebOptionsCallBack.aspx?SourceSystem=PRISM&ResourceType=Document&ResourceID=%d&language=1&DisplayMode=2'
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
        match = re.search(r"href='/HousePublications/Redirector\.aspx\?RedirectUrl=([^'>]+)'>Bill Votes</A>", callpage.read())
        if not match:
            print "Couldn't find Bill Votes link in get_by_callback_id"
            raise Bill.DoesNotExist()
        votesurl = urllib.unquote(match.group(1))
        votespage = urllib2.urlopen(votesurl)
        match = re.search(r'Parl=(\d+)&Ses=(\d+)&Bill=C(\d+[A-Z]?)', votesurl)
        if not match:
            raise Bill.DoesNotExist("Couldn't parse Bill Votes link")
        session = Session.objects.get(parliamentnum=match.group(1), sessnum=match.group(2))
        billnum = 'C-%s' % match.group(3)
        #match = re.search(r'([A-Z]+-\d+)\s+(.+)', votediv.string.strip())
        #billnum, billname = match.group(1), match.group(2)
        try:
            bill = self.get_query_set().get(number=billnum, sessions=session)
        except Bill.DoesNotExist:
            votesoup = BeautifulSoup(votespage.read())
            votediv = votesoup.find('div', 'VotesBill')
            billname = votediv.string.strip()
            bill = Bill(name=billname, number=billnum)
            bill.session = session
            bill.save()
        InternalXref(schema='bill_callbackid', int_value=callback, target_id=bill.id).save()
        return bill
        

class Bill(models.Model):
    
    name = models.CharField(max_length=500)
    number = models.CharField(max_length=10)
    number_only = models.SmallIntegerField()
    sessions = models.ManyToManyField(Session)
    legisinfo_url = models.URLField(blank=True, null=True, verify_exists=False)
    privatemember = models.NullBooleanField()
    sponsor_member = models.ForeignKey(ElectedMember, blank=True, null=True)
    sponsor_politician= models.ForeignKey(Politician, blank=True, null=True)
    law = models.NullBooleanField()
    status = models.CharField(max_length=200, blank=True)
    added = models.DateField(default=datetime.date.today, db_index=True)
    
    objects = BillManager()
    
    class Meta:
        ordering = ('number_only',)
    
    def __unicode__(self):
        return "%s - %s" % (self.number, self.name)
        
    @models.permalink
    def get_absolute_url(self):
        return ('parliament.bills.views.bill', [self.id])
        
    def save(self, *args, **kwargs):
        if not self.number_only:
            self.number_only = int(re.sub(r'\D', '', self.number))
        if getattr(self, 'privatemember', None) is None:
            self.privatemember = bool(self.number_only >= 200)
        super(Bill, self).save(*args, **kwargs)
        if getattr(self, '_save_session', None):
            self.sessions.add(self._save_session)

    def save_sponsor_activity(self):
        if self.sponsor_politician:
            activity.save_activity(
                obj=self,
                politician=self.sponsor_politician,
                date=self.added - datetime.timedelta(days=1), # we generally pick it up the day after it appears
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
        membervotes = self.membervote_set.select_related('member', 'member__party').all()
        parties = defaultdict(lambda: defaultdict(int))
        
        for mv in membervotes:
            if mv.member.party.name != 'Independent':
                parties[mv.member.party][mv.vote] += 1
        
        partyvotes = {}
        for party in parties:
            votes = sorted(parties[party].items(), key=lambda i: i[1])
            partyvotes[party] = votes[-1][0]
            PartyVote(party=party, votequestion=self, vote=partyvotes[party]).save()
        
        for mv in membervotes:
            if mv.member.party.name != 'Independent' \
              and mv.vote != partyvotes[mv.member.party] \
              and mv.vote in ('Y', 'N') \
              and partyvotes[mv.member.party] in ('Y', 'N'):
                mv.dissent = True
                mv.save()
            
    @models.permalink
    def get_absolute_url(self):
        return ('parliament.bills.views.vote', [self.id])

VOTE_CHOICES = [
    ('Y', 'Yea'),
    ('N', 'Nay'),
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
    vote = models.CharField(max_length=1, choices=VOTE_CHOICES)
    
    def __unicode__(self):
        return u'%s voted %s on %s' % (self.party, self.get_vote_display(), self.votequestion)