import datetime
import json
import re

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction

import requests

from parliament.bills.models import Bill, BillText, LEGISINFO_BILL_ID_URL
from parliament.core.models import Session, Politician, ElectedMember
from parliament.imports import CannotScrapeException
from parliament.imports.billtext import get_plain_bill_text

import logging
logger = logging.getLogger(__name__)

LEGISINFO_DETAIL_URL = 'https://www.parl.ca/LegisInfo/en/bill/%(parlnum)s-%(sessnum)s/%(billnumber)s/json'
LEGISINFO_JSON_LIST_URL = 'https://www.parl.ca/legisinfo/en/bills/json?parlsession=%(sessid)s'

def _parse_date(d):
    return datetime.date(*[int(x) for x in d[:10].split('-')])

class BillData:
    """
    A wrapper for JSON bill data from parl.ca. 
    """

    def __init__(self, jsondata):
        self._d = jsondata

    def __getitem__(self, key):
        v = self._d[key]
        if key.endswith('DateTime') or key.endswith('Date'):
            # for now we're only providing dates, not datetimes
            return _parse_date(v) if v else v
        return v

    def __str__(self):
        return "<BillData %s (%s-%s)>" % (
            self['NumberCode'], self['ParliamentNumber'], self['SessionNumber'])

    def __repr__(self):
        return str(self)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    @property
    def is_detailed(self):
        return bool(self.get('BillStages'))

    @property
    def detailed_json_url(self):
        return LEGISINFO_DETAIL_URL % {
            'parlnum': self['ParliamentNumber'],
            'sessnum': self['SessionNumber'],
            'billnumber': self['BillNumberFormatted'].lower()
        }

    def get_detailed(self):
        resp = requests.get(self.detailed_json_url)
        resp.raise_for_status()
        rj = resp.json()
        assert len(rj) == 1
        self._d = rj[0]
        return self

def get_bill_list(session: Session) -> list[BillData]:
    url = LEGISINFO_JSON_LIST_URL % dict(sessid=session.id)
    resp = requests.get(url)
    resp.raise_for_status()
    jd = resp.json()
    return [BillData(item) for item in jd]
    
@transaction.atomic
def import_bills(session: Session):
    bill_list = get_bill_list(session)
    for bd in bill_list:
        _import_bill(bd, session)

def import_bill_by_id(legisinfo_id: int | str) -> Bill:
    """Imports a single bill based on its LEGISinfo id."""
    
    # This request should redirect from an ID to a canonical URL, which we 
    # can then tack /json on to
    url = LEGISINFO_BILL_ID_URL % {'id': legisinfo_id, 'lang': 'en'}
    resp = requests.get(url)
    resp.raise_for_status()

    if not re.search(r'-\d+$', resp.url):
        raise Bill.DoesNotExist("Could not find bill for LEGISinfo ID %s" % legisinfo_id)

    detail_url = resp.url + '/json'
    resp = requests.get(detail_url)
    resp.raise_for_status()

    rj = resp.json()
    assert len(rj) == 1
    bd = BillData(rj[0])

    session = Session.objects.get(parliamentnum=bd['ParliamentNumber'],
        sessnum=bd['SessionNumber'])
    # print "Importing bill ID %s" % legisinfo_id
    return _import_bill(bd, session)

def _update(obj, field, value):
    if value is None:
        return
    if not isinstance(value, datetime.date):
        value = str(value)
    if getattr(obj, field) != value:
        setattr(obj, field, value)
        obj._changed = True

class OldBillException(Exception):
    pass

def _import_bill(bd: BillData, session: Session) -> Bill:
    if session.parliamentnum < 37:
        raise OldBillException()
    
    if not bd.is_detailed:
        # Right now it looks like the data model requires one request per bill;
        # I can at some point look closer to see if there's a method at looking
        # at the small version of the resource to see if things have changed
        # enough to warrant fetching the full version
        bd.get_detailed()

    billnumber = bd['NumberCode']
    try:
        bill = Bill.objects.get(number=billnumber, session=session)
    except Bill.DoesNotExist:
        bill = Bill(number=billnumber, session=session)
        bill._changed = True

    _update(bill, 'name_en', bd['LongTitleEn'])

    if not bill.status_code:
        bill._newbill = True

    _update(bill, 'name_fr', bd['LongTitleFr'])
    _update(bill, 'short_title_en', bd['ShortTitleEn'])
    _update(bill, 'short_title_fr', bd['ShortTitleFr'])

    if not bill.sponsor_politician and bill.number[0] == 'C' and bd.get('SponsorPersonId'):
        # We don't deal with Senate sponsors yet
        pol_id = bd['SponsorPersonId']
        try:
            bill.sponsor_politician = Politician.objects.get_by_parl_mp_id(pol_id)
        except Politician.DoesNotExist:
            logger.error("Couldn't find sponsor politician for bill %s, pol ID %s, name %s" % (
                bill.number, pol_id, bd.get('SponsorPersonName')))
        bill._changed = True
        try:
            bill.sponsor_member = ElectedMember.objects.get_by_pol(politician=bill.sponsor_politician,
                                                                   session=session)
        except Exception:
            logger.error("Couldn't find ElectedMember for bill %s, pol %r" %
                         (bill.number, bill.sponsor_politician))

    introduced = bd['PassedHouseFirstReadingDateTime']
    if bd['PassedSenateFirstReadingDateTime'] and ((not introduced) or bd['PassedSenateFirstReadingDateTime'] < introduced):
        introduced = bd['PassedSenateFirstReadingDateTime']
    _update(bill, 'introduced', introduced)

    status_name = bd['StatusName']
    status_code = Bill.STATUS_STRING_TO_STATUS_CODE.get(status_name)
    if status_code:
        _update(bill, 'status_code', status_code)
    else:
        logger.error("Unknown bill status %s" % status_name)

    _update(bill, 'status_date', bd['LatestBillEventDateTime'])

    try:
        _update(bill, 'text_docid', bd['Publications'][-1]['PublicationId'])
    except IndexError:
        pass

    _update(bill, 'legisinfo_id', bd['Id'])
    _update(bill, 'library_summary_available', bd.get('IsFullLegislativeSummaryAvailable'))

    billstages_json = json.dumps(bd.get('BillStages'))
    if session.parliamentnum >= 39:
        _update(bill, 'billstages_json', billstages_json)

    if getattr(bill, '_changed', False):
        bill.save()

    if bd.get('SimilarBills'):
        for similar in bd['SimilarBills']:
            if similar['ParliamentNumber'] < 37:
                # Don't import super-old bills, it complicates things
                continue
            try:
                similar_bill = Bill.objects.get_by_legisinfo_id(similar['Id'])
                bill.similar_bills.add(similar_bill)
            except Bill.DoesNotExist:
                logger.error("Couldn't find similar bill %s while importing %s", similar['NumberCode'], bill)

    if getattr(bill, '_newbill', False) and not session.end:
        bill.save_sponsor_activity()

    if bill.text_docid and not BillText.objects.filter(docid=bill.text_docid).exists():
        try:
            summary_en, text_en = get_plain_bill_text(bill)
            BillText.objects.create(
                bill=bill,
                docid=bill.text_docid,
                text_en=text_en,
                summary_en=summary_en
            )
            bill.save()  # to trigger search indexing
        except CannotScrapeException:
            logger.warning("Could not get bill text for %s" % bill)

    return bill
            