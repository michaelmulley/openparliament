import sys, re, urllib, urllib2, os
from collections import defaultdict
import urlparse
import itertools

from django.db import transaction, models
from django.db.models import Count
from django.core.files import File
from BeautifulSoup import BeautifulSoup

from parliament.imports import hans
from parliament.core import parsetools
from parliament.core.models import *
from parliament.hansards.models import Hansard, HansardCache, Statement
from parliament.elections.models import Election, Candidacy

def update_hansards():
    hansards_from_calendar()
    parse_all_hansards()

def load_pol_pics():
    for pol in Politician.objects.exclude(parlpage='').filter(models.Q(headshot__isnull=True) | models.Q(headshot='')):
        print "#%d: %s" % (pol.id, pol)
        print pol.parlpage
        soup = BeautifulSoup(urllib2.urlopen(pol.parlpage))
        img = soup.find('img', id='MasterPage_MasterPage_BodyContent_PageContent_Content_TombstoneContent_TombstoneContent_ucHeaderMP_imgPhoto')
        if not img:
            img = soup.find('img', id="ctl00_cphContent_imgParliamentarianPicture")
            if not img:
                raise Exception("Didn't work for %s" % pol.parlpage)
        imgurl = img['src']
        if '?' not in imgurl: # no query string
            imgurl = urllib.quote(imgurl.encode('utf8')) # but there might be accents!
        imgurl = urlparse.urljoin(pol.parlpage, imgurl)
        try:
            test = urllib2.urlopen(imgurl)
            content = urllib.urlretrieve(imgurl)
        except Exception, e:
            print "ERROR ON %s" % pol
            print e
            print imgurl
            continue
        #filename = urlparse.urlparse(imgurl).path.split('/')[-1]
        pol.headshot.save(str(pol.id) + ".jpg", File(open(content[0])), save=True)
        pol.save()

def delete_invalid_pol_pics():
    from PIL import Image
    for p in Politician.objects.exclude(headshot__isnull=True).exclude(headshot=''):
        try:
            Image.open(p.headshot)
        except IOError:
            print "DELETING image for %s" % p
            os.unlink(p.headshot.path)
            p.headshot = None
            p.save()


def parse_all_hansards(): 
    for hansard in Hansard.objects.all().annotate(scount=Count('statement')).exclude(scount__gt=0).order_by('date'):
        try:
            print "Trying %d %s... " % (hansard.id, hansard)
            hans.parseAndSave(hansard)
            print "SUCCESS for %s" % hansard
        except Exception, e:
            print "******* FAILURE **********"
            print "ERROR: %s" % e
            print "EXCEPTION TYPE: %s" % e.__class__
            cache = HansardCache.objects.get(hansard=hansard.id)
            print "HANSARD %d: %s" % (cache.hansard.id, cache.hansard)
            print "FILE: %s" % cache.filename
            print "URL: %s" % cache.hansard.url
        
        
def export_words(outfile, queryset=None):
    if queryset is None:
        queryset = Statement.objects.all()
    for s in queryset.values_list(('text'), flat=True):
        outfile.write(s)
        outfile.write("\n")

def corpus_for_pol(pol):
    
    r_splitter = re.compile(r'[^\w\'\-]+', re.UNICODE)
    states = Statement.objects.filter(member__politician=pol).order_by('time', 'sequence')
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

def hansards_from_calendar(session=None):
    if not session:
        session = Session.objects.current()
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
    raise Exception("Not yet implemented after ElectedMember refactor")
    for winner in Candidacy.objects.filter(election=election, elected=True):
        candidate = winner.candidate
        try:
            member = ElectedMember.objects.get(session=session, politician=candidate)
        except ElectedMember.DoesNotExist:
            ElectedMember(session=session, politician=candidate, party=winner.party, riding=winner.riding).save()
            
def copy_members(from_session, to_session):
    raise Exception("Not yet implemented after ElectedMember refactor")
    for member in ElectedMember.objects.filter(session=from_session):
        ElectedMember(session=to_session, politician=member.politician, party=member.party, riding=member.riding).save()

def populate_parlid():
    for pol in Politician.objects.filter(parlpage__isnull=False):
        if pol.parlpage:
            match = re.search(r'Key=(\d+)', pol.parlpage)
            if not match:
                raise Exception("didn't match on %s" % pol.parlpage)
            pol.parlwebid = int(match.group(1))
            pol.save()

def replace_links(old, new):
    if old.__class__ != new.__class__:
        raise Exception("Are old and new the same type?")
    for relation in old._meta.get_all_related_objects():
        if relation.model == old.__class__:
            print "Relation to self!"
            continue
        print relation.field.name
        relation.model._default_manager.filter(**{relation.field.name: old}).update(**{relation.field.name: new})
    for relation in old._meta.get_all_related_many_to_many_objects():
        if relation.model == old.__class__:
            print "Relation to self!"
            continue
        print relation.field.name
        for obj in relation.model._default_manager.filter(**{relation.field.name: old}):
            getattr(obj, relation.field.name).remove(old)    
            getattr(obj, relation.field.name).add(new)        

def _merge_pols(good, bad):
    #ElectedMember.objects.filter(politician=bad).update(politician=good)
    #Candidacy.objects.filter(candidate=bad).update(candidate=good)
    #Statement.objects.filter(politician=bad).update(politician=good)
    replace_links(old=bad, new=good)
    seen = set()
    for xref in InternalXref.objects.filter(schema__startswith='pol_', target_id=bad.id):
        if (xref.int_value, xref.text_value) in seen:
            xref.delete()
        else:
            xref.target_id = good.id
            xref.save()
            seen.add((xref.int_value, xref.text_value))
    bad.delete()

#REFORM = (Party.objects.get(pk=25), Party.objects.get(pk=1), Party.objects.get(pk=28), Party.objects.get(pk=26))

def merge_by_party(parties):
    raise Exception("Not yet implemented after ElectedMember refactor")
    
    dupelist = Politician.objects.values('name').annotate(namecount=Count('name')).filter(namecount__gt=1).order_by('-namecount')
    for dupeset in dupelist:
        pols = Politician.objects.filter(name=dupeset['name'])
        province = None
        fail = False
        events = []
        for pol in pols:
            for em in ElectedMember.objects.filter(politician=pol):
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
        for em in ElectedMember.objects.filter(politician=pol):
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
    for em in ElectedMember.objects.filter(politician=good):
        print em
    for cand in Candidacy.objects.filter(candidate=good):
        print cand
    print "Enter ID of bad pol object: ",
    badid = int(sys.stdin.readline().strip())
    bad = Politician.objects.get(pk=badid)
    for em in ElectedMember.objects.filter(politician=bad):
        print em
    for cand in Candidacy.objects.filter(candidate=bad):
        print cand
    print "Go? (y/n) ",
    yn = sys.stdin.readline().strip().lower()
    if yn == 'y':
        _merge_pols(good, bad)
        print "Done!"
        
def fix_mac():
    """ Alexa Mcdonough -> Alexa McDonough """
    for p in Politician.objects.filter(models.Q(name_family__startswith='Mc')|models.Q(name_family__startswith='Mac')):
        nforig = p.name_family
        def mac_replace(match):
            return match.group(1) + match.group(2).upper()
        p.name_family = re.sub(r'(Ma?c)([a-z])', mac_replace, p.name_family)
        print p.name + " -> ",
        p.name = p.name.replace(nforig, p.name_family)
        print p.name
        p.save()
        
def check_for_feeds(urls):
    for url in urls:
        try:
            response = urllib2.urlopen(url)
        except Exception, e:
            print "ERROR on %s" % url
            print e
            continue
        soup = BeautifulSoup(response.read())
        for feed in soup.findAll('link', type='application/rss+xml'):
            print "FEED ON %s" % url
            print feed