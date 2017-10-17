import datetime
import urllib2

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction

from lxml import etree

from parliament.bills.models import Bill, BillInSession, BillText, BillEvent
from parliament.committees.models import Committee, CommitteeMeeting
from parliament.core.models import Session, Politician, ElectedMember
from parliament.hansards.models import Document
from parliament.imports import CannotScrapeException
from parliament.imports.billtext import get_plain_bill_text

import logging
logger = logging.getLogger(__name__)

LEGISINFO_XML_LIST_URL = 'http://parl.gc.ca/LegisInfo/Home.aspx?language=E&ParliamentSession=%(sessid)s&Page=%(page)s&Mode=1&download=xml'
LEGISINFO_SINGLE_BILL_URL = 'http://www.parl.gc.ca/LegisInfo/BillDetails.aspx?Language=E&Mode=1&billId=%(legisinfo_id)s&download=xml'

def _parse_date(d):
    return datetime.date(*[int(x) for x in d[:10].split('-')])

def _get_previous_session(session):
    try:
        return Session.objects.filter(start__lt=session.start)\
            .order_by('-start')[0]
    except IndexError:
        return None

@transaction.atomic
def import_bills(session):
    """Import bill data from LegisInfo for the given session.
    
    session should be a Session object"""
    
    previous_session = _get_previous_session(session)
        
    page = 0
    fetch_next_page = True
    while fetch_next_page:
        page += 1
        url = LEGISINFO_XML_LIST_URL % {
            'sessid': session.id,
            'page': page
        }
        tree = etree.parse(urllib2.urlopen(url))
        bills = tree.xpath('//Bill')
        if len(bills) < 500:
            # As far as I can tell, there's no indication within the XML file of
            # whether it's a partial or complete list, but it looks like the 
            # limit for one file/page is 500.
            fetch_next_page = False

        for lbill in bills:
            try:
                _import_bill(lbill, session, previous_session)
            except urllib2.HTTPError as e:
                logger.error("%s %s" % (e, getattr(e, 'url', '(no url)')))

    return True

def import_bill_by_id(legisinfo_id):
    """Imports a single bill based on its LEGISinfo id."""
    
    url = LEGISINFO_SINGLE_BILL_URL % {'legisinfo_id': legisinfo_id}
    try:
        tree = etree.parse(urllib2.urlopen(url))
    except urllib2.HTTPError:
        raise Bill.DoesNotExist("HTTP error retrieving bill")
    bill = tree.xpath('/Bill')
    assert len(bill) == 1
    bill = bill[0]

    sessiontag = bill.xpath('ParliamentSession')[0]
    session = Session.objects.get(parliamentnum=int(sessiontag.get('parliamentNumber')),
        sessnum=int(sessiontag.get('sessionNumber')))
    return _import_bill(bill, session)

def _update(obj, field, value):
    if value is None:
        return
    if not isinstance(value, datetime.date):
        value = unicode(value)
    if getattr(obj, field) != value:
        setattr(obj, field, value)
        obj._changed = True

def _import_bill(lbill, session, previous_session=None):
    #lbill should be an ElementTree Element for the Bill tag

    if previous_session is None:
        previous_session = _get_previous_session(session)

    lbillnumber = lbill.xpath('BillNumber')[0]
    billnumber = (lbillnumber.get('prefix') + '-' + lbillnumber.get('number')
        + lbillnumber.get('suffix', ''))
    try:
        bill = Bill.objects.get(number=billnumber, sessions=session)
        bis = bill.billinsession_set.get(session=session)
    except Bill.DoesNotExist:
        bill = Bill(number=billnumber)
        bis = BillInSession(bill=bill, session=session)
        bill._changed = True
        bis._changed = True
        bill.set_temporary_session(session)

    _update(bill, 'name_en', lbill.xpath('BillTitle/Title[@language="en"]')[0].text)

    if not bill.status_code:
        # This is presumably our first import of the bill; check if this
        # looks like a reintroduced bill and we want to merge with an
        # older Bill object.
        bill._newbill = True
        try:
            if previous_session:
                mergebill = Bill.objects.get(sessions=previous_session,
                                             number=bill.number,
                                             name_en__iexact=bill.name_en)

                if bill.id:
                    # If the new bill has already been saved, let's not try
                    # to merge automatically
                    logger.error("Bill %s may need to be merged. IDs: %s %s" %
                                 (bill.number, bill.id, mergebill.id))
                else:
                    logger.warning("Merging bill %s" % bill.number)
                    bill = mergebill
                    bis.bill = bill
        except Bill.DoesNotExist:
            # Nothing to merge
            pass

    _update(bill, 'name_fr', lbill.xpath('BillTitle/Title[@language="fr"]')[0].text)
    _update(bill, 'short_title_en', lbill.xpath('ShortTitle/Title[@language="en"]')[0].text)
    _update(bill, 'short_title_fr', lbill.xpath('ShortTitle/Title[@language="fr"]')[0].text)

    if not bis.sponsor_politician and bill.number[0] == 'C' and lbill.xpath('SponsorAffiliation/@id'):
        # We don't deal with Senate sponsors yet
        pol_id = int(lbill.xpath('SponsorAffiliation/@id')[0])
        try:
            bis.sponsor_politician = Politician.objects.get_by_parl_id(pol_id)
        except Politician.DoesNotExist:
            logger.error("Couldn't find sponsor politician for bill %s, pol ID %s" % (bill.number, pol_id))
        bis._changed = True
        try:
            bis.sponsor_member = ElectedMember.objects.get_by_pol(politician=bis.sponsor_politician,
                                                                   session=session)
        except Exception:
            logger.error("Couldn't find ElectedMember for bill %s, pol %r" %
                         (bill.number, bis.sponsor_politician))
        if not bill.sponsor_politician:
            bill.sponsor_politician = bis.sponsor_politician
            bill.sponsor_member = bis.sponsor_member
            bill._changed = True

    _update(bis, 'introduced', _parse_date(lbill.xpath('BillIntroducedDate')[0].text))
    if not bill.introduced:
        bill.introduced = bis.introduced

    try:
        status_code = lbill.xpath('Events')[0].get('laagCurrentStage')
        if status_code == '':
            status_code = 'Introduced'
        _update(bill, 'status_code', status_code)
        if status_code not in Bill.STATUS_CODES:
            logger.error("Unknown bill status code %s" % status_code)
        #_update(bill, 'status_date', _parse_date(
        #    lbill.xpath('Events/LastMajorStageEvent/Event/@date')[0]))
        status_dates = [_parse_date(d) for d in lbill.xpath('Events/LegislativeEvents/Event/@date')]
        _update(bill, 'status_date', max(status_dates))
    except IndexError:
        # Some older bills don't have status information
        pass

    try:
        _update(bill, 'text_docid', int(
            lbill.xpath('Publications/Publication/@id')[-1]))
    except IndexError:
        pass

    _update(bis, 'legisinfo_id', int(lbill.get('id')))

    if getattr(bill, '_changed', False):
        bill.save()
    if getattr(bis, '_changed', False):
        bis.bill = bis.bill # bizarrely, the django orm makes you do this
        bis.save()        

    for levent in lbill.xpath('Events/LegislativeEvents/Event'):
        source_id = int(levent.get('id'))
        if BillEvent.objects.filter(source_id=source_id).exists():
            continue

        try:
            status_en = levent.xpath('Status/Title[@language="en"]/text()')[0]
            status_fr = levent.xpath('Status/Title[@language="fr"]/text()')[0]
        except IndexError:
            logger.debug("No status present in billevent: %s", etree.tostring(levent))
            continue

        event = BillEvent(
            source_id=source_id,
            bis=bis,
            date=_parse_date(levent.get('date')),
            institution='S' if levent.get('chamber') == 'SEN' else 'C',
            status_en=status_en,
            status_fr=status_fr
        )

        if event.institution == 'C':
            hansard_num = levent.get('meetingNumber')
            try:
                event.debate = Document.debates.get(session=bis.session, number=hansard_num)
            except Document.DoesNotExist:
                logger.info(u"Could not associate BillEvent for %s with Hansard#%s" % (bill, hansard_num))
                continue

            for lcommittee in levent.xpath('Committee'):
                acronym = lcommittee.get('accronym')
                if acronym and acronym != 'WHOL':
                    event.save()
                    try:
                        committee = Committee.objects.get_by_acronym(acronym, bis.session)
                        for number in lcommittee.xpath('CommitteeMeetings/CommitteeMeeting/@number'):
                            event.committee_meetings.add(
                                CommitteeMeeting.objects.get(committee=committee, number=int(number), session=bis.session)
                            )
                    except ObjectDoesNotExist:
                        logger.exception("Could not import committee meetings: %s" % etree.tostring(lcommittee))
                        continue
        event.save()

    if getattr(bill, '_newbill', False) and not session.end:
        bill.save_sponsor_activity()

    if bill.text_docid and not BillText.objects.filter(docid=bill.text_docid).exists():
        try:
            BillText.objects.create(
                bill=bill,
                docid=bill.text_docid,
                text_en=get_plain_bill_text(bill)
            )
            bill.save()  # to trigger search indexing
        except CannotScrapeException:
            logger.warning(u"Could not get bill text for %s" % bill)

    return bill
            