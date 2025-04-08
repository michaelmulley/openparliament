"""This file is mostly a dumping ground for various largely one-off data import and massaging routines.

Production code should NOT import from this file."""

import sys, re, urllib.request, urllib.parse, urllib.error, urllib.request, urllib.error, urllib.parse, os, csv
from collections import defaultdict
import urllib.parse

from django.db import transaction, models
from django.db.models import Count
from django.core.files import File
from django.conf import settings

from parliament.core.models import *
from parliament.hansards.models import Statement
from parliament.elections.models import Election, Candidacy

def load_pol_pic(pol):
    print("#%d: %s" % (pol.id, pol))
    print(pol.parlpage)
    soup = BeautifulSoup(urllib.request.urlopen(pol.parlpage))
    img = soup.find('img', id='MasterPage_MasterPage_BodyContent_PageContent_Content_TombstoneContent_TombstoneContent_ucHeaderMP_imgPhoto')
    if not img:
        raise Exception("Didn't work for %s" % pol.parlpage)
    imgurl = img['src']
    if '?' not in imgurl: # no query string
        imgurl = urllib.parse.quote(imgurl.encode('utf8')) # but there might be accents!
    if 'BlankMPPhoto' in imgurl:
        print("Blank photo")
        return
    imgurl = urllib.parse.urljoin(pol.parlpage, imgurl)
    test = urllib.request.urlopen(imgurl)
    content = urllib.request.urlretrieve(imgurl)
    #filename = urlparse.urlparse(imgurl).path.split('/')[-1]
    pol.headshot.save(str(pol.id) + ".jpg", File(open(content[0])), save=True)
    pol.save()

def delete_invalid_pol_pics():
    from PIL import Image
    for p in Politician.objects.exclude(headshot__isnull=True).exclude(headshot=''):
        try:
            Image.open(p.headshot)
        except IOError:
            print("DELETING image for %s" % p)
            os.unlink(p.headshot.path)
            p.headshot = None
            p.save()
            
def delete_invalid_pol_urls():
    for pol in Politician.objects.filter(politicianinfo__schema='web_site').distinct():
        site = pol.info()['web_site']
        try:
            urllib.request.urlopen(site)
            print("Success for %s" % site)
        except urllib.error.URLError as e:
            print("REMOVING %s " % site)
            print(e)
            pol.politicianinfo_set.filter(schema='web_site').delete()
        
def export_words(outfile, queryset=None):
    if queryset is None:
        queryset = Statement.objects.all()
    for s in queryset.iterator():
        outfile.write(s.text_plain().encode('utf8'))
        outfile.write("\n")

def export_tokenized_words(outfile, queryset):
    for word in text_utils.qs_token_iterator(queryset, statement_separator="/"):
        outfile.write(word.encode('utf8'))
        outfile.write(' ')

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
            for entry in index.items():
                SparkIndex(token=entry[0], count=entry[1], bucket=bucketidx).save()
            index = defaultdict(int)
            bucketcount = 0
            bucketidx += 1
            
def populate_members_by():
    for by in Election.objects.filter(byelection=True):
        print(str(by))
        print("Enter session IDs: ", end=' ')
        sessions = [Session.objects.get(pk=int(x)) for x in sys.stdin.readline().strip().split()]
        for session in sessions:
            print(str(session))
            x = sys.stdin.readline()
            populate_members(by, session)

def populate_members(election, session, start_date):
    """ Label all winners in an election Members for the subsequent session. """
    for winner in Candidacy.objects.filter(election=election, elected=True):
        candidate = winner.candidate
        try:
            member = ElectedMember.objects.get(politician=candidate,
                party=winner.party, riding=winner.riding, end_date__isnull=True)
            member.sessions.add(session)
        except ElectedMember.DoesNotExist:
            em = ElectedMember.objects.create(
                politician=candidate, start_date=start_date,
                party=winner.party, riding=winner.riding)
            em.sessions.add(session)
            
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

def replace_links(old, new, allow_self_relation=False):
    if old.__class__ != new.__class__:
        raise Exception("Are old and new the same type?")
    fields = [f for f in old._meta.get_fields() if (f.auto_created and not f.concrete)]
    for relation in fields:
        if relation.one_to_many:
            if relation.related_model == old.__class__:
                if allow_self_relation:
                    print("self: %r" % relation)
                    continue
                else:
                    raise Exception("Relation to self!")
            print(f"{relation.related_model.__name__}.{relation.field.name}")
            print(
                relation.related_model._default_manager.filter(**{relation.field.name: old}).update(**{relation.field.name: new})
            )
        elif relation.many_to_many:
            if relation.related_model == old.__class__:
                raise Exception("Relation to self!")
            print(relation.field.name)
            for obj in relation.related_model._default_manager.filter(**{relation.field.name: old}):
                getattr(obj, relation.field.name).remove(old)    
                getattr(obj, relation.field.name).add(new)        

def _merge_pols(good, bad):
    #ElectedMember.objects.filter(politician=bad).update(politician=good)
    #Candidacy.objects.filter(candidate=bad).update(candidate=good)
    #Statement.objects.filter(politician=bad).update(politician=good)
    replace_links(old=bad, new=good)
    print(bad.delete())

    pi_seen = set()
    for pi in good.politicianinfo_set.all():
        val = (pi.schema, pi.value)
        if val in pi_seen:
            pi.delete()
        pi_seen.add(val)

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
                    print("%s not acceptable" % em.party)
                    break
                if em.session in events:
                    fail = True
                    print("Duplicate event for %s, %s" % (pol, em.session))
                    events.append(em.session)
                    break
                if province is None:
                    province = em.riding.province
                elif em.riding.province != province:
                    fail = True
                    print("Province doesn't match for %s: %s, %s" % (pol, em.riding.province, province))
            for cand in Candidacy.objects.filter(candidate=pol):
                if cand.party not in parties:
                    fail = True
                    print("%s not acceptable" % cand.party)
                    break
                if cand.election in events:
                    fail = True
                    print("Duplicate event for %s, %s" % (pol, cand.election))
                    events.append(cand.election)
                    break
                if province is None:
                    province = cand.riding.province
                elif cand.riding.province != province:
                    fail = True
                    print("Province doesn't match for %s: %s, %s" % (pol, cand.riding.province, province))
        if not fail:
            good = pols[0]
            bads = pols[1:]
            for bad in bads:
                _merge_pols(good, bad)
            print("Merged %s" % good)

def merge_polnames():
    
    def _printout(pol):
        for em in ElectedMember.objects.filter(politician=pol):
            print(em)
        for cand in Candidacy.objects.filter(candidate=pol):
            print(cand)
    while True:
        print("Space-separated list of IDs: ", end=' ')
        ids = sys.stdin.readline().strip().split()
        good = Politician.objects.get(pk=int(ids[0]))
        bads = [Politician.objects.get(pk=int(x)) for x in ids[1:]]
        _printout(good)
        for bad in bads: _printout(bad)
        print("Go? (y/n) ", end=' ')
        yn = sys.stdin.readline().strip().lower()
        if yn == 'y':
            for bad in bads:
                _merge_pols(good, bad)
            while True:
                print("Alternate name? ", end=' ')
                alt = sys.stdin.readline().strip()
                if len(alt) > 5:
                    good.add_alternate_name(alt)
                else:
                    break
            print("Done!")
    
@transaction.atomic
def merge_pols():
    print("Enter ID of primary pol object: ")
    goodid = int(input().strip())
    good = Politician.objects.get(pk=goodid)
    for em in ElectedMember.objects.filter(politician=good):
        print(em)
    for cand in Candidacy.objects.filter(candidate=good):
        print(cand)
    print("Enter ID of bad pol object: ")
    badid = int(input().strip())
    bad = Politician.objects.get(pk=badid)
    for em in ElectedMember.objects.filter(politician=bad):
        print(em)
    for cand in Candidacy.objects.filter(candidate=bad):
        print(cand)
    print("Go? (y/n) ")
    yn = input().strip().lower()
    if yn == 'y':
        _merge_pols(good, bad)
        print("Done!")
        
def fix_mac():
    """ Alexa Mcdonough -> Alexa McDonough """
    for p in Politician.objects.filter(models.Q(name_family__startswith='Mc')|models.Q(name_family__startswith='Mac')):
        nforig = p.name_family
        def mac_replace(match):
            return match.group(1) + match.group(2).upper()
        p.name_family = re.sub(r'(Ma?c)([a-z])', mac_replace, p.name_family)
        print(p.name + " -> ", end=' ')
        p.name = p.name.replace(nforig, p.name_family)
        print(p.name)
        p.save()
        
def check_for_feeds(urls):
    for url in urls:
        try:
            response = urllib.request.urlopen(url)
        except Exception as e:
            print("ERROR on %s" % url)
            print(e)
            continue
        soup = BeautifulSoup(response.read())
        for feed in soup.findAll('link', type='application/rss+xml'):
            print("FEED ON %s" % url)
            print(feed)
            
def twitter_from_csv(infile):
    reader = csv.DictReader(infile)
    session = Session.objects.current()
    for line in reader:
        name = line['Name'].decode('utf8')
        surname = line['Surname'].decode('utf8')
        pol = Politician.objects.get_by_name(' '.join([name, surname]), session=session)
        PoliticianInfo.objects.get_or_create(politician=pol, schema='twitter', value=line['twitter'].strip())
        
def twitter_to_list():
    from twitter import Twitter
    twit = Twitter(settings.TWITTER_USERNAME, settings.TWITTER_PASSWORD)
    for t in PoliticianInfo.objects.filter(schema='twitter'):
        twit.openparlca.mps.members(id=t.value)
        
def slugs_for_pols(qs=None):
    if not qs:
        qs = Politician.objects.current()
    for pol in qs.filter(slug=''):
        slug = slugify(pol.name)
        if Politician.objects.filter(slug=slug).exists():
            print("WARNING: %s already taken" % slug)
        else:
            pol.slug = slug
            pol.save()
            
def wikipedia_from_freebase():
    import freebase
    for info in PoliticianInfo.sr_objects.filter(schema='freebase_id'):
        query = {
            'id': info.value,
            'key': [{
                'namespace': '/wikipedia/en_id',
                'value': None
            }]
        }
        result = freebase.mqlread(query)
        if result:
            # freebase.api.mqlkey.unquotekey
            wiki_id = result['key'][0]['value']
            info.politician.set_info('wikipedia_id', wiki_id)
            
def freebase_id_from_parl_id():
    import freebase
    import time
    for info in PoliticianInfo.sr_objects.filter(schema='parl_id').order_by('value'):
        if PoliticianInfo.objects.filter(politician=info.politician, schema='freebase_id').exists():
            continue
        query = {
            'type': '/base/cdnpolitics/member_of_parliament',
            'id': [],
            'key': {
                'namespace': '/source/ca/gov/house',
                'value': info.value
            }
        }
        result = freebase.mqlread(query)
        print("result: %s" % result)
        #time.sleep(1)
        if not result:
            try:
                print("Nothing for %s (%s)" % (info.value, info.politician))
            except:
                pass
        else:
            freebase_id = result['id'][0]
            PoliticianInfo(politician=info.politician, schema='freebase_id', value=freebase_id).save()
            print("Saved: %s" % freebase_id)
            
def pol_urls_to_ids():
    for pol in Politician.objects.exclude(parlpage=''):
        if 'Item' in pol.parlpage and 'parlinfo_id' not in pol.info():
            print(pol.parlpage)
            match = re.search(r'Item=([A-Z0-9-]+)', pol.parlpage)
            pol.set_info('parlinfo_id', match.group(1))
        if 'Key' in pol.parlpage and 'parl_id' not in pol.info():
            print(pol.parlpage)
            match = re.search(r'Key=(\d+)', pol.parlpage)
            pol.set_info('parl_id', match.group(1))
            
def export_statements(outfile, qs):
    for s in qs.iterator():
        if not s.speaker:
            outfile.write(s.text_plain().encode('utf8'))
            outfile.write("\n")

def add_missing_genders():
    for pol in Politician.objects.current().filter(gender=''):
        print(pol)
        gender = input().strip().upper()
        assert gender in ('M', 'F')
        pol.gender = gender
        pol.save()

def print_changed_mps(previous_date):
    prev_members = ElectedMember.objects.on_date(previous_date)
    current_members = ElectedMember.objects.current()
    for prev in prev_members:
        cur = current_members.get(riding=prev.riding)
        if prev.politician != cur.politician:
            print(prev.riding)
            print("%s => %s" % (prev.politician.name, cur.politician.name))
