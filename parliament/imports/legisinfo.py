import urllib, urllib2, re
import datetime

from BeautifulSoup import BeautifulSoup
from django.db import models, transaction
from django.core.mail import mail_admins
import feedparser

from parliament.core.models import InternalXref, Politician, ElectedMember, Session
from parliament.bills.models import Bill
from parliament.activity import utils as activity

LEGISINFO_LIST_URL = 'http://www2.parl.gc.ca/Sites/LOP/LEGISINFO/index.asp?Language=E&List=list&Type=0&Chamber=C&StartList=2&EndList=2000&Session=%d'
LEGISINFO_DETAIL_URL = 'http://www2.parl.gc.ca/Sites/LOP/LEGISINFO/index.asp?Language=E&Session=%d&query=%d&List=toc'


@transaction.commit_on_success
def import_bills(session):
    previous_session = Session.objects.filter(start__lt=session.start)\
        .order_by('-start')[0] # yes, this will raise an exception if there's no older session on record
    
    legis_sess = InternalXref.objects.get(target_id=session.id, schema='session_legisin').int_value
    listurl = LEGISINFO_LIST_URL % legis_sess
    listpage = urllib2.urlopen(listurl).read()
    
    r_listlink = re.compile(r'<a href="index\.asp\?Language=E&Session=\d+&query=(\d+)&List=toc">\s*(C-\d+[A-Z]?)\s*</a>', re.UNICODE)
    for match in r_listlink.finditer(listpage):
        legisinfoid = int(match.group(1))
        billnumber_full = match.group(2)
        try:
            bill = Bill.objects.get(sessions=session, number=billnumber_full)
        except Bill.DoesNotExist:
            bill = None
        
        if not getattr(bill, 'legisinfo_url', None):
            # Not yet in the database. Go parse.
            detailurl = LEGISINFO_DETAIL_URL % (legis_sess, legisinfoid)
            try:
                detailpage = urllib2.urlopen(detailurl).read().decode('windows-1252')
            except urllib2.URLError, e:
                print "ERROR: URLError on %s" % detailurl
                print e
                continue
            match = re.search(r'<td>\s*(An [aA]ct.+?)<br', detailpage)
            if not match:
                soup = BeautifulSoup(detailpage)
                try:
                    billname = unicode(soup.find(text=billnumber_full).next.next.next)
                    print "WARNING: soupmatching bill name as %s" % billname
                except Exception, e:
                    print "Couldn't parse bill name at %s" % detailurl
                    print e
                    continue
            else:
                billname = match.group(1)[:500]
            
            # Is this a reintroduced bill?
            merging = False
            try:
                mergebill = Bill.objects.get(sessions=previous_session, number=billnumber_full, name__iexact=billname)
                if not bill:
                    bill = mergebill
                    merging = True
                    print "MERGING BILL"
                else:
                    mail_admins('Bills may need to be merged', "%s: ids %s %s" % (billnumber_full, mergebill.id, bill.id))
            except Bill.DoesNotExist:
                # Nope. New bill.
                if not bill:
                    bill = Bill(number=billnumber_full, name=billname)
                    bill.session = session
            
            if bill.session != session:
                bill.sessions.add(session)
            
            bill.legisinfo_url = detailurl
            
            membermatch = re.search(r'<font color="#005500"><b><a href=.http://www2\.parl\.gc\.ca/parlinfo/Files/Parliamentarian\.aspx\?Item=([A-Z0-9-]+?)&.+?>(.+?)<', detailpage)
            if membermatch:
                try:
                    bill.sponsor_politician = Politician.objects.get_by_parlinfo_id(membermatch.group(1))
                except models.ObjectDoesNotExist:
                    membername = membermatch.group(2)
                    membername = re.sub(r'\(.+?\)', '', membername) # parens
                    membername = re.sub(r'.+ Hon\.', '', membername) # honorific
                    try:
                        bill.sponsor_politician = Politician.objects.get_by_name(membername.strip(), session=session)
                        bill.sponsor_politician.save_parlinfo_id(membermatch.group(1))
                    except (Politician.DoesNotExist, Politician.MultipleObjectsReturned):
                        print "WARNING: Could not identify politician for bill %s" % billnumber_full
                if bill.sponsor_politician:
                    try:
                        bill.sponsor_member = ElectedMember.objects.get_by_pol(politician=bill.sponsor_politician,
                            session=session)
                    except:
                        print "WARNING: Couldn't find member for politician %s" % bill.sponsor_politician
            bill.save()
            bill.save_sponsor_activity()
    return True

LEGISINFO_STATUS_URL = 'http://www2.parl.gc.ca/Sites/LOP/LEGISINFO/RSSFeeds.asp?parlNumber=%(parliamentnum)s&session=%(sessnum)s&chamber=C&billNumber=%(billnum)s&billLetter=&language=E'

def get_bill_feed(bill):
    return feedparser.parse(LEGISINFO_STATUS_URL % {
        'parliamentnum': bill.session.parliamentnum,
        'sessnum': bill.session.sessnum,
        'billnum': bill.number.replace('C-', '')
    })

def update_bill_status(bill):
    feed = get_bill_feed(bill)
    try:
        status = feed['items'][-1]['title']
    except Exception, e:
        print "Error parsing feed for %s" % bill
        print e
        return False
    bill.status = status
    bill.law = bool('Royal Assent' in status)
    bill.save()
    
def update_statuses_for_session(session, private_members_also=True):
    print "Updating statuses for %s" % session
    bills = Bill.objects.filter(sessions=session).exclude(law=True).exclude(number_only=1)
    if not private_members_also:
        bills = bills.exclude(privatemember=True)
    for bill in bills:
        update_bill_status(bill)