import xml.etree.ElementTree as etree
import urllib2
import datetime

from django.db import transaction

from parliament.bills.models import Bill, VoteQuestion, MemberVote
from parliament.core.models import ElectedMember, Politician, Riding, Session
from parliament.core import parsetools

import logging
logger = logging.getLogger(__name__)

VOTELIST_URL = 'http://www2.parl.gc.ca/HouseChamberBusiness/Chambervotelist.aspx?Language=E&Mode=1&Parl=%(parliamentnum)s&Ses=%(sessnum)s&xml=True&SchemaVersion=1.0'
VOTEDETAIL_URL = 'http://www2.parl.gc.ca/HouseChamberBusiness/Chambervotedetail.aspx?Language=%(lang)s&Mode=1&Parl=%(parliamentnum)s&Ses=%(sessnum)s&FltrParl=%(parliamentnum)s&FltrSes=%(sessnum)s&vote=%(votenum)s&xml=True'

@transaction.commit_on_success
def import_votes(session=None):
    if session is None:
        session = Session.objects.current()
    votelisturl = VOTELIST_URL % {'parliamentnum' : session.parliamentnum, 'sessnum': session.sessnum}
    votelistpage = urllib2.urlopen(votelisturl)
    tree = etree.parse(votelistpage)
    root = tree.getroot()
    votelist = root.findall('Vote')
    votelist.reverse() # We want to process earlier votes first, just for the order they show up in the activity feed
    for vote in votelist:
        votenumber = int(vote.attrib['number'])
        if VoteQuestion.objects.filter(session=session, number=votenumber).count():
            continue
        print "Processing vote #%s" % votenumber
        votequestion = VoteQuestion(
            number=votenumber,
            session=session,
            date=datetime.date(*(int(x) for x in vote.attrib['date'].split('-'))),
            yea_total=int(vote.find('TotalYeas').text),
            nay_total=int(vote.find('TotalNays').text),
            paired_total=int(vote.find('TotalPaired').text))
        if sum((votequestion.yea_total, votequestion.nay_total)) < 100:
            logger.error("Fewer than 100 votes on vote#%s" % votenumber)
            continue
        decision = vote.find('Decision').text
        if decision == 'Agreed to':
            votequestion.result = 'Y'
        elif decision == 'Negatived':
            votequestion.result = 'N'
        elif decision == 'Tie':
            votequestion.result = 'T'
        else:
            raise Exception("Couldn't process vote result %s in %s" % (decision, votelisturl))
        if vote.find('RelatedBill') is not None:
            billnumber = vote.find('RelatedBill').attrib['number']
            try:
                votequestion.bill = Bill.objects.get(sessions=session, number=billnumber)
            except Bill.DoesNotExist:
                votequestion.bill = Bill.objects.create_temporary_bill(session=session, number=billnumber)
                logger.warning("Temporary bill %s created for vote %s" % (billnumber, votenumber))

        # Now get the detailed results
        votedetailurl = VOTEDETAIL_URL % {'parliamentnum' : session.parliamentnum,
                'lang': 'E',
                'sessnum': session.sessnum,
                'votenum': votenumber }
        try:
            votedetailpage = urllib2.urlopen(votedetailurl)
            detailtree = etree.parse(votedetailpage)
        except Exception, e:
            print "ERROR on %s" % votedetailurl
            print e
            continue
        detailroot = detailtree.getroot()
        votequestion.description = parsetools.etree_extract_text(detailroot.find('Context')).strip()

        votedetailurl_fr = VOTEDETAIL_URL % {'parliamentnum' : session.parliamentnum,
                'lang': 'F',
                'sessnum': session.sessnum,
                'votenum': votenumber }
        try:
            votedetailpage_fr = urllib2.urlopen(votedetailurl_fr)
            detailtree_fr = etree.parse(votedetailpage_fr)
        except Exception, e:
            print "ERROR on %s" % votedetailurl_fr
            print e
            continue
        detailroot_fr = detailtree_fr.getroot()
        votequestion.description_fr = parsetools.etree_extract_text(detailroot_fr.find('Context')).strip()

        
        # Okay, save the question, start processing members.
        votequestion.save()
        for voter in detailroot.findall('Participant'):
            name = voter.find('FirstName').text + ' ' + voter.find('LastName').text
            riding = Riding.objects.get_by_name(voter.find('Constituency').text)
            pol = Politician.objects.get_by_name(name=name, session=session, riding=riding)
            member = ElectedMember.objects.get_by_pol(politician=pol, date=votequestion.date)
            rvote = voter.find('RecordedVote')
            if rvote.find('Yea').text == '1':
                ballot = 'Y'
            elif rvote.find('Nay').text == '1':
                ballot = 'N'
            elif rvote.find('Paired').text == '1':
                ballot = 'P'
            else:
                raise Exception("Couldn't parse RecordedVote for %s in vote %s" % (name, votenumber))
            MemberVote(member=member, politician=pol, votequestion=votequestion, vote=ballot).save()
        votequestion.label_absent_members()
        votequestion.label_party_votes()
        for mv in votequestion.membervote_set.all():
            mv.save_activity()
    return True