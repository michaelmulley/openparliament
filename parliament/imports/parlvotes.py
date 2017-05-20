import datetime

from lxml import etree
import requests

from django.db import transaction

from parliament.bills.models import Bill, VoteQuestion, MemberVote
from parliament.core.models import ElectedMember, Politician, Riding, Session
from parliament.core import parsetools

import logging
logger = logging.getLogger(__name__)

VOTELIST_URL = 'http://www.ourcommons.ca/Parliamentarians/{lang}/HouseVotes/ExportVotes?output=XML'
VOTEDETAIL_URL = 'http://www.ourcommons.ca/Parliamentarians/en/HouseVotes/ExportDetailsVotes?output=XML&parliament={parliamentnum}&session={sessnum}&vote={votenumber}'
#VOTELIST_URL = 'http://www2.parl.gc.ca/HouseChamberBusiness/Chambervotelist.aspx?Language=E&Mode=1&Parl=%(parliamentnum)s&Ses=%(sessnum)s&xml=True&SchemaVersion=1.0'
#VOTEDETAIL_URL = 'http://www2.parl.gc.ca/HouseChamberBusiness/Chambervotedetail.aspx?Language=%(lang)s&Mode=1&Parl=%(parliamentnum)s&Ses=%(sessnum)s&FltrParl=%(parliamentnum)s&FltrSes=%(sessnum)s&vote=%(votenum)s&xml=True'

@transaction.atomic
def import_votes(session=None):
    if session is None:
        session = Session.objects.current()
    elif session != Session.objects.current():
        raise Exception("FIXME only current session supported in VOTELIST_URL for now")
    
    votelisturl_en = VOTELIST_URL.format(lang='en')
    resp = requests.get(votelisturl_en)
    resp.raise_for_status()
    root = etree.fromstring(resp.content)

    votelisturl_fr = VOTELIST_URL.format(lang='fr')
    resp = requests.get(votelisturl_fr)
    resp.raise_for_status()
    root_fr = etree.fromstring(resp.content)

    votelist = root.findall('VoteParticipant')
    for vote in votelist:
        votenumber = int(vote.findtext('DecisionDivisionNumber'))
        if VoteQuestion.objects.filter(session=session, number=votenumber).count():
            continue
        print "Processing vote #%s" % votenumber
        date = vote.findtext('DecisionEventDateTime')
        date = datetime.datetime.strptime(date, '%Y-%m-%dT%H:%M:%S').date()
        votequestion = VoteQuestion(
            number=votenumber,
            session=session,
            date=date,
            yea_total=int(vote.findtext('DecisionDivisionNumberOfYeas')),
            nay_total=int(vote.findtext('DecisionDivisionNumberOfNays')),
            paired_total=int(vote.findtext('DecisionDivisionNumberOfPaired')))
        if sum((votequestion.yea_total, votequestion.nay_total)) < 100:
            logger.error("Fewer than 100 votes on vote#%s" % votenumber)
        decision = vote.findtext('DecisionResultName')
        if decision in ('Agreed to', 'Agreed To'):
            votequestion.result = 'Y'
        elif decision == 'Negatived':
            votequestion.result = 'N'
        elif decision == 'Tie':
            votequestion.result = 'T'
        else:
            raise Exception("Couldn't process vote result %s in %s" % (decision, votelisturl))
        if vote.findtext('BillNumberCode'):
            billnumber = vote.findtext('BillNumberCode')
            try:
                votequestion.bill = Bill.objects.get(sessions=session, number=billnumber)
            except Bill.DoesNotExist:
                votequestion.bill = Bill.objects.create_temporary_bill(session=session, number=billnumber)
                logger.warning("Temporary bill %s created for vote %s" % (billnumber, votenumber))

        votequestion.description_en = vote.findtext('DecisionDivisionSubject')
        try:
            votequestion.description_fr = root_fr.xpath(
                'VoteParticipant/DecisionDivisionNumber[text()=%s]/../DecisionDivisionSubject/text()'
                % votenumber)[0]
        except Exception:
            logger.exception("Couldn't get french description for vote %s" % votenumber)

        # Okay, save the question, start processing members.
        votequestion.save()

        detailurl = VOTEDETAIL_URL.format(parliamentnum=session.parliamentnum,
            sessnum=session.sessnum, votenumber=votenumber)
        resp = requests.get(detailurl)
        resp.raise_for_status()
        detailroot = etree.fromstring(resp.content)

        for voter in detailroot.findall('VoteParticipant'):
            name = voter.find('FirstName').text + ' ' + voter.find('LastName').text
            riding = Riding.objects.get_by_name(voter.find('ConstituencyName').text)
            pol = Politician.objects.get_by_name(name=name, session=session, riding=riding)
            member = ElectedMember.objects.get_by_pol(politician=pol, date=votequestion.date)
            if voter.find('Yea').text == '1':
                ballot = 'Y'
            elif voter.find('Nay').text == '1':
                ballot = 'N'
            elif voter.find('Paired').text == '1':
                ballot = 'P'
            else:
                raise Exception("Couldn't parse RecordedVote for %s in vote %s" % (name, votenumber))
            MemberVote(member=member, politician=pol, votequestion=votequestion, vote=ballot).save()
        votequestion.label_absent_members()
        votequestion.label_party_votes()
        for mv in votequestion.membervote_set.all():
            mv.save_activity()
    return True