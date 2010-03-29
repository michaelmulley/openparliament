import urllib, urllib2, re

from django.db import models
from BeautifulSoup import BeautifulSoup

from parliament.core.models import Session, InternalXref

CALLBACK_URL = 'http://www2.parl.gc.ca/HousePublications/GetWebOptionsCallBack.aspx?SourceSystem=PRISM&ResourceType=Document&ResourceID=%d&language=1&DisplayMode=2'
class BillManager(models.Manager):
    
    def get_by_callback_id(self, callback, session):
        try:
            xref = InternalXref.objects.get(schema='bill_callbackid', int_value=callback)
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
        votesoup = BeautifulSoup(votespage.read())
        votediv = votesoup.find('div', 'VotesBill')
        match = re.search(r'([A-Z]+-\d+)\s+(.+)', votediv.string.strip())
        billnum, billname = match.group(1), match.group(2)
        try:
            bill = self.get_query_set().get(number=billnum, session=session)
        except Bill.DoesNotExist:
            bill = Bill(name=billname, number=billnum, session=session)
            bill.save()
        InternalXref(schema='bill_callbackid', int_value=callback, target_id=bill.id).save()
        return bill
        

class Bill(models.Model):
    
    name = models.CharField(max_length=500)
    number = models.CharField(max_length=10)
    session = models.ForeignKey(Session)
    
    objects = BillManager()
    
    def __unicode__(self):
        return "%s - %s" % (self.number, self.name)
        
    @models.permalink
    def get_absolute_url(self):
        return ('parliament.bills.views.bill', [self.id])