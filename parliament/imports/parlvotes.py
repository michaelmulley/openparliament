import datetime

from lxml import etree
import requests

from django.db import transaction

from parliament.bills.models import Bill, VoteQuestion, MemberVote
from parliament.core.models import ElectedMember, Politician, Riding, Session
from parliament.core import parsetools

import logging
logger = logging.getLogger(__name__)

VOTELIST_URL = 'https://www.ourcommons.ca/members/{lang}/votes/xml'
VOTEDETAIL_URL = 'https://www.ourcommons.ca/members/en/votes/{parliamentnum}/{sessnum}/{votenumber}/xml'

@transaction.atomic
def import_votes():
    votelisturl_en = VOTELIST_URL.format(lang='en')
    resp = requests.get(votelisturl_en)
    resp.raise_for_status()
    root = etree.fromstring(resp.content)

    votelisturl_fr = VOTELIST_URL.format(lang='fr')
    resp = requests.get(votelisturl_fr)
    resp.raise_for_status()
    root_fr = etree.fromstring(resp.content)

    votelist = root.findall('Vote')
    for vote in votelist:
        votenumber = int(vote.findtext('DecisionDivisionNumber'))
        session = Session.objects.get(
            parliamentnum=int(vote.findtext('ParliamentNumber')),
            sessnum=int(vote.findtext('SessionNumber'))
        )
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
                'Vote/DecisionDivisionNumber[text()=%s]/../DecisionDivisionSubject/text()'
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
            pol = Politician.objects.get_by_parl_mp_id(voter.find('PersonId').text,
                session=session, riding_name=voter.find('ConstituencyName').text)
            # name = (voter.find('PersonOfficialFirstName').text 
            #     + ' ' + voter.find('PersonOfficialLastName').text)
            # riding = Riding.objects.get_by_name(voter.find('ConstituencyName').text)
            # pol = Politician.objects.get_by_name(name=name, session=session, riding=riding)
            member = ElectedMember.objects.get_by_pol(politician=pol, date=votequestion.date)
            if voter.find('IsVoteYea').text == 'true':
                ballot = 'Y'
            elif voter.find('IsVoteNay').text == 'true':
                ballot = 'N'
            elif voter.find('IsVotePaired').text == 'true':
                ballot = 'P'
            else:
                raise Exception("Couldn't parse RecordedVote for %s in vote %s" % (name, votenumber))
            MemberVote(member=member, politician=pol, votequestion=votequestion, vote=ballot).save()
        votequestion.label_absent_members()
        votequestion.label_party_votes()
        for mv in votequestion.membervote_set.all():
            mv.save_activity()
    return True