import urllib, urllib2, re

from BeautifulSoup import BeautifulSoup
from django.db import models

from parliament.core.models import InternalXref, Politician, ElectedMember
from parliament.bills.models import Bill

LEGISINFO_LIST_URL = 'http://www2.parl.gc.ca/Sites/LOP/LEGISINFO/index.asp?Language=E&List=list&Type=0&Chamber=C&StartList=2&EndList=2000&Session=%d'
LEGISINFO_DETAIL_URL = 'http://www2.parl.gc.ca/Sites/LOP/LEGISINFO/index.asp?Language=E&Session=%d&query=%d&List=toc'
def import_bills(session):
    legis_sess = InternalXref.objects.get(target_id=session.id, schema='session_legisin').int_value
    listurl = LEGISINFO_LIST_URL % legis_sess
    listpage = urllib2.urlopen(listurl).read()
    r_listlink = re.compile(r'<a href="index\.asp\?Language=E&Session=\d+&query=(\d+)&List=toc">\s*C-(\d+)\s*</a>', re.UNICODE)
    for match in r_listlink.finditer(listpage):
        legisinfoid = int(match.group(1))
        billnumber = int(match.group(2))
        try:
            bill = Bill.objects.get(session=session, number="C-%s" % billnumber)
        except Bill.DoesNotExist:
            bill = Bill(session=session, number="C-%s" % billnumber)
        
        if not bill.legisinfo_url:
            # We don't have extended legisinfo information. Go and parse it.
            detailurl = LEGISINFO_DETAIL_URL % (legis_sess, legisinfoid)
            try:
                detailpage = urllib2.urlopen(detailurl).read().decode('windows-1252')
            except urllib2.URLError, e:
                print "ERROR: URLError on %s" % detailurl
                print e
                continue
            bill.legisinfo_url = detailurl
            #if not bill.name:
            match = re.search(r'<td>\s*(An Act.+?)<br', detailpage)
            if not match:
                print "Couldn't parse bill name at %s" % detailurl
                continue
            bill.name = match.group(1)[:500]
            membermatch = re.search(r'<font color="#005500"><b><a href=.http://www2\.parl\.gc\.ca/parlinfo/Files/Parliamentarian\.aspx\?Item=([A-Z0-9-]+?)&', detailpage)
            if membermatch:
                try:
                    bill.sponsor_politician = Politician.objects.get_by_parlinfo_id(membermatch.group(1))
                    bill.sponsor_member = ElectedMember.objects.get_by_pol(politician=bill.sponsor_politician,
                      session=session)
                except models.ObjectDoesNotExist:
                     print "WARNING: Could not identify member for bill C-%s" % billnumber
            if billnumber >= 200:
                bill.privatemember = True
            else:
                bill.privatemember = False
            bill.save()
    