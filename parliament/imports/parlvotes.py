import xml.etree.ElementTree as etree
import urllib2
import datetime

from django.db import transaction

from parliament.bills.models import Bill, VoteQuestion, MemberVote
from parliament.core.models import ElectedMember, Politician, Riding, Session
from parliament.core import parsetools

VOTELIST_URL = 'http://www2.parl.gc.ca/HouseChamberBusiness/Chambervotelist.aspx?Language=E&Mode=1&Parl=%(parliamentnum)s&Ses=%(sessnum)s&xml=True&SchemaVersion=1.0'
VOTEDETAIL_URL = 'http://www2.parl.gc.ca/HouseChamberBusiness/Chambervotedetail.aspx?Language=E&Mode=1&Parl=%(parliamentnum)s&Ses=%(sessnum)s&FltrParl=%(parliamentnum)s&FltrSes=%(sessnum)s&vote=%(votenum)s&xml=True'

@transaction.commit_on_success
def import_votes(session=None):
    if session is None:
        session = Session.objects.current()
    votelisturl = VOTELIST_URL % {'parliamentnum' : session.parliamentnum, 'sessnum': session.sessnum}
    votelistpage = urllib2.urlopen(votelisturl)
    tree = etree.parse(votelistpage)
    root = tree.getroot()
    for vote in root.findall('Vote'):
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
            try:
                votequestion.bill = Bill.objects.get(session=session, number=vote.find('RelatedBill').attrib['number'])
            except Bill.DoesNotExist:
                print "ERROR: Could not find bill for vote %s" % votenumber
                continue
        
        # Now get the detailed results
        votedetailurl = VOTEDETAIL_URL % {'parliamentnum' : session.parliamentnum,
                'sessnum': session.sessnum,
                'votenum': votenumber }
        votedetailpage = urllib2.urlopen(votedetailurl)
        detailtree = etree.parse(votedetailpage)
        detailroot = detailtree.getroot()
        votequestion.description = parsetools.etree_extract_text(detailroot.find('Context')).strip()

        
        # Okay, save the question, start processing members.
        votequestion.save()
        for voter in detailroot.findall('Participant'):
            name = voter.find('FirstName').text + ' ' + voter.find('LastName').text
            riding = Riding.objects.getByName(voter.find('Constituency').text)
            pol = Politician.objects.getByName(name=name, session=session, riding=riding)
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
    return True