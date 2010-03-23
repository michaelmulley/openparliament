from mulley.parliament.models import *
import sys, re, urllib2
from django.db import transaction
from django.db.models import Count
from BeautifulSoup import BeautifulSoup
from mulley.parliament.imports import hans
from mulley.parliament import parsetools
from collections import defaultdict

def export_words(outfile, queryset=None):
    if queryset is None:
        queryset = Statement.objects.all()
    for s in queryset.values_list(('text'), flat=True):
        outfile.write(s)
        outfile.write("\n")

def corpus_for_pol(pol):
    
    r_splitter = re.compile(r'[^\w\'\-]+', re.UNICODE)
    states = Statement.objects.filter(member__member=pol).order_by('time', 'sequence')
    words = []
    for s in states:
        words.extend(re.split(r_splitter, s.text))
    return [w for w in words if len(w) > 0]

r_splitter = re.compile(r'[^\w\'\-]+', re.UNICODE)
def spark_index(bucketsize, bigrams=False):
    
    
    index = defaultdict(int)
    bucketidx = 0
    bucketcount = 0
    for s in Statement.objects.all().order_by('time'):
        tokens = re.split(r_splitter, s.text.lower())
        for t in tokens:
            if t != '':
                index[t[:15]] += 1
        bucketcount += len(tokens)
        if bucketcount >= bucketsize:
            # save
            for entry in index.iteritems():
                SparkIndex(token=entry[0], count=entry[1], bucket=bucketidx).save()
            index = defaultdict(int)
            bucketcount = 0
            bucketidx += 1
            
def get_parlinfo_ids(polset=Politician.objects.filter(parlpage__icontains='webinfo.parl')):
    
    for pol in polset:
        page = urllib2.urlopen(pol.parlpage)
        soup = BeautifulSoup(page)
        parlinfolink = soup.find('a', id='MasterPage_MasterPage_BodyContent_PageContent_Content_TombstoneContent_TombstoneContent_ucHeaderMP_hlFederalExperience')
        if not parlinfolink:
            print "Couldn't find on %s" % parlpage
        else:
            match = re.search(r'Item=(.+?)&', parlinfolink['href'])
            pol.saveParlinfoID(match.group(1))
            print "Saved for %s" % pol

def normalize_hansard_urls():
    for h in Hansard.objects.all():
        normalized = parsetools.normalizeHansardURL(h.url)
        if normalized != h.url:
            h.url = normalized
            h.save()

def cache_hansards():
    for h in Hansard.objects.filter(url__icontains='http'):
        try:
            print "Loading %s..." % h
            hans.loadHansard(h)
        except Exception, e:
            print "Failure %s" % e

def hansards_from_calendar(session):
    SKIP_HANSARDS = {
    'http://www2.parl.gc.ca/HousePublications/Publication.aspx?Language=E&Mode=2&Parl=36&Ses=2&DocId=2332160' : True,
    }
    url = 'http://www2.parl.gc.ca/housechamberbusiness/chambersittings.aspx?View=H&Parl=%d&Ses=%d&Language=E&Mode=2' % (session.parliamentnum, session.sessnum)
    print "Getting calendar..."
    soup = BeautifulSoup(urllib2.urlopen(url))
    print "Calendar retrieved."
    cal = soup.find('div', id='ctl00_PageContent_calTextCalendar')
    for link in cal.findAll('a', href=True):
        hurl = 'http://www2.parl.gc.ca' + link['href']
        if hurl in SKIP_HANSARDS:
            continue
        hurl = hurl.replace('Mode=2&', 'Mode=1&')
        print "Loading url %s" % hurl
        try:
            hans.loadHansard(url=hurl, session=session)
        except Exception, e:
            print "Failure %s" % e

def populate_members_by():
    for by in Election.objects.filter(byelection=True):
        print unicode(by)
        print "Enter session IDs: ",
        sessions = [Session.objects.get(pk=int(x)) for x in sys.stdin.readline().strip().split()]
        for session in sessions:
            print unicode(session)
            x = sys.stdin.readline()
            populate_members(by, session)

def populate_members(election, session):
    """ Label all winners in an election Members for the subsequent session. """
    for winner in Candidacy.objects.filter(election=election, elected=True):
        candidate = winner.candidate
        try:
            member = ElectedMember.objects.get(session=session, member=candidate)
        except ElectedMember.DoesNotExist:
            ElectedMember(session=session, member=candidate, party=winner.party, riding=winner.riding).save()
            
def copy_members(from_session, to_session):
    for member in ElectedMember.objects.filter(session=from_session):
        ElectedMember(session=to_session, member=member.member, party=member.party, riding=member.riding).save()

def populate_parlid():
    for pol in Politician.objects.filter(parlpage__isnull=False):
        if pol.parlpage:
            match = re.search(r'Key=(\d+)', pol.parlpage)
            if not match:
                raise Exception("didn't match on %s" % pol.parlpage)
            pol.parlwebid = int(match.group(1))
            pol.save()

def _merge_pols(good, bad):
    ElectedMember.objects.filter(member=bad).update(member=good)
    Candidacy.objects.filter(candidate=bad).update(candidate=good)
    bad.delete()

#REFORM = (Party.objects.get(pk=25), Party.objects.get(pk=1), Party.objects.get(pk=28), Party.objects.get(pk=26))

def merge_by_party(parties):
    
    dupelist = Politician.objects.values('name').annotate(namecount=Count('name')).filter(namecount__gt=1).order_by('-namecount')
    for dupeset in dupelist:
        pols = Politician.objects.filter(name=dupeset['name'])
        province = None
        fail = False
        events = []
        for pol in pols:
            for em in ElectedMember.objects.filter(member=pol):
                if em.party not in parties:
                    fail = True
                    print "%s not acceptable" % em.party
                    break
                if em.session in events:
                    fail = True
                    print "Duplicate event for %s, %s" % (pol, em.session)
                    events.append(em.session)
                    break
                if province is None:
                    province = em.riding.province
                elif em.riding.province != province:
                    fail = True
                    print "Province doesn't match for %s: %s, %s" % (pol, em.riding.province, province)
            for cand in Candidacy.objects.filter(candidate=pol):
                if cand.party not in parties:
                    fail = True
                    print "%s not acceptable" % cand.party
                    break
                if cand.election in events:
                    fail = True
                    print "Duplicate event for %s, %s" % (pol, cand.election)
                    events.append(cand.election)
                    break
                if province is None:
                    province = cand.riding.province
                elif cand.riding.province != province:
                    fail = True
                    print "Province doesn't match for %s: %s, %s" % (pol, cand.riding.province, province)
        if not fail:
            good = pols[0]
            bads = pols[1:]
            for bad in bads:
                _merge_pols(good, bad)
            print "Merged %s" % good

def merge_polnames():
    
    def _printout(pol):
        for em in ElectedMember.objects.filter(member=pol):
            print em
        for cand in Candidacy.objects.filter(candidate=pol):
            print cand
    while True:
        print "Space-separated list of IDs: ",
        ids = sys.stdin.readline().strip().split()
        good = Politician.objects.get(pk=int(ids[0]))
        bads = [Politician.objects.get(pk=int(x)) for x in ids[1:]]
        _printout(good)
        for bad in bads: _printout(bad)
        print "Go? (y/n) ",
        yn = sys.stdin.readline().strip().lower()
        if yn == 'y':
            for bad in bads:
                _merge_pols(good, bad)
            while True:
                print "Alternate name? ",
                alt = sys.stdin.readline().strip()
                if len(alt) > 5:
                    good.addAlternateName(alt)
                else:
                    break
            print "Done!"
    
@transaction.commit_on_success
def merge_pols():
    print "Enter ID of primary pol object: ",
    goodid = int(sys.stdin.readline().strip())
    good = Politician.objects.get(pk=goodid)
    for em in ElectedMember.objects.filter(member=good):
        print em
    for cand in Candidacy.objects.filter(candidate=good):
        print cand
    print "Enter ID of bad pol object: ",
    badid = int(sys.stdin.readline().strip())
    bad = Politician.objects.get(pk=badid)
    for em in ElectedMember.objects.filter(member=bad):
        print em
    for cand in Candidacy.objects.filter(candidate=bad):
        print cand
    print "Go? (y/n) ",
    yn = sys.stdin.readline().strip().lower()
    if yn == 'y':
        _merge_pols(good, bad)
        print "Done!"