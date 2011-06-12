import datetime
import urllib, urllib2

from django.db import transaction

from lxml import etree

from parliament.bills.models import Bill
from parliament.core.models import Session, Politician, ElectedMember

import logging
logger = logging.getLogger(__name__)

LEGISINFO_XML_LIST_URL = 'http://parl.gc.ca/LegisInfo/Home.aspx?language=E&Parl=%(parliament)s&Ses=%(session)s&Page=%(page)s&Mode=1&download=xml'

@transaction.commit_on_success
def import_bills(session):
    """Import bill data from LegisInfo for the given session.
    
    session should be a Session object"""
    
    previous_session = Session.objects.filter(start__lt=session.start)\
        .order_by('-start')[0] # yes, this will raise an exception if there's no older session on record
        
    page = 0
    fetch_next_page = True
    while fetch_next_page:
        page += 1
        url = LEGISINFO_XML_LIST_URL % {
            'parliament': session.parliamentnum,
            'session': session.sessnum,
            'page': page
        }
        tree = etree.parse(urllib2.urlopen(url))
        bills = tree.xpath('//Bill')
        if len(bills) < 500:
            # As far as I can tell, there's no indication within the XML file of
            # whether it's a partial or complete list, but it looks like the 
            # limit for one file/page is 500.
            fetch_next_page = False
            
        def update(field, value):
            if value is None:
                return
            if not isinstance(value, datetime.date):
                value = unicode(value)
            if getattr(bill, field) != value:
                setattr(bill, field, value)
            bill._changed = True
            
        def parse_date(d):
            return datetime.date(*[int(x) for x in d[:10].split('-')])
            
        for lbill in bills:
            lbillnumber = lbill.xpath('BillNumber')[0]
            billnumber = lbillnumber.get('prefix') + '-' + lbillnumber.get('number') \
                + lbillnumber.get('suffix', '')
            try:
                bill = Bill.objects.get(number=billnumber, sessions=session)
            except Bill.DoesNotExist:
                bill = Bill(number=billnumber)
                bill.session = session
                bill._changed = True
                
            update('name', lbill.xpath('BillTitle/Title[@language="en"]')[0].text)
            
            if not bill.status:
                # This is presumably our first import of the bill; check if this
                # looks like a reintroduced bill and we want to merge with an 
                # older Bill object.
                bill._newbill = True
                try:
                    mergebill = Bill.objects.get(sessions=previous_session,
                        number=bill.number,
                        name__iexact=bill.name)
                    
                    if bill.id:
                        # If the new bill has already been saved, let's not try
                        # to merge automatically
                        logger.error("Bill %s may need to be merged. IDs: %s %s" %
                            (bill.number, bill.id, mergebill.id))
                    else:
                        logger.warning("Merging bill %s" % bill.number)
                        bill = mergebill
                        bill.sessions.add(session)
                except Bill.DoesNotExist:
                    # Nothing to merge
                    pass
                
            update('name_fr', lbill.xpath('BillTitle/Title[@language="fr"]')[0].text)
            update('short_title_en', lbill.xpath('ShortTitle/Title[@language="en"]')[0].text)
            update('short_title_fr', lbill.xpath('ShortTitle/Title[@language="fr"]')[0].text)
            
            if not bill.sponsor_politician and bill.number[0] == 'C':
                # We don't deal with Senate sponsors yet
                pol_id = int(lbill.xpath('SponsorAffiliation/@id')[0])
                bill.sponsor_politician = Politician.objects.get_by_parl_id(pol_id)
                bill._changed = True
                try:
                    bill.sponsor_member = ElectedMember.objects.get_by_pol(politician=bill.sponsor_politician,
                            session=session)
                except:
                    logger.error("Couldn't find ElectedMember for bill %s, pol %r" %
                        (bill.number, bill.sponsor_politician))
                        
            update('introduced', parse_date(lbill.xpath('BillIntroducedDate')[0].text))
            update('status', 
                lbill.xpath('Events/LastMajorStageEvent/Event/Status/Title[@language="en"]')[0].text)
            update('status_fr', 
                lbill.xpath('Events/LastMajorStageEvent/Event/Status/Title[@language="fr"]')[0].text)
            update('status_date', parse_date(
                lbill.xpath('Events/LastMajorStageEvent/Event/@date')[0]))
            
            try:
                update('text_docid', int(
                    lbill.xpath('Publications/Publication/@id')[-1]))
            except IndexError:
                pass
                
            if bill._changed:
                bill.save()
                if getattr(bill, '_newbill', False):
                    bill.save_sponsor_activity()
            