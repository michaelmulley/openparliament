from decimal import Decimal
import re
import urllib2

from BeautifulSoup import BeautifulSoup
from django.db import transaction
import requests

from parliament.core import parsetools
from parliament.core.models import Riding, Party, Politician, ElectedMember
from parliament.elections.models import Candidacy

@transaction.atomic
def import_ec_results(election, url="http://enr.elections.ca/DownloadResults.aspx",
        allow_preliminary=False):
    """Import an election from the text format used on enr.elections.ca
    (after the 2011 general election)"""

    preliminary_results = {}
    validated_results = {}

    for line in requests.get(url).content.split('\n'):
        line = line.decode('utf-8').split('\t')
        edid = line[0]
        if not edid.isdigit():
            continue
        result_type = line[3]
        if result_type == 'preliminary':
            preliminary_results.setdefault(edid, []).append(line)
        elif result_type == 'validated':
            validated_results.setdefault(edid, []).append(line)
        else:
            raise Exception("%s not an acceptable type" % result_type)

    if (not allow_preliminary) and len(preliminary_results) > len(validated_results):
        raise Exception("Some results are only preliminary, stopping")

    if len(validated_results) > len(preliminary_results):
        raise Exception("Huh?")

    for edid in preliminary_results:
        if edid in validated_results:
            lines = validated_results[edid]
        elif allow_preliminary:
            lines = preliminary_results[edid]
        else:
            assert False

        riding = Riding.objects.get(current=True, edid=edid)

        for line in lines:
            last_name = line[5]
            first_name = line[7]
            party_name = line[8]
            votetotal = int(line[10])
            votepercent = Decimal(line[11])

            try:
                party = Party.objects.get_by_name(party_name)
            except Party.DoesNotExist:
                print "No party found for %r" % party_name
                print "Please enter party ID:"
                party = Party.objects.get(pk=raw_input().strip())
                party.add_alternate_name(party_name)
                print repr(party.name)
                
            Candidacy.objects.create_from_name(
                first_name=first_name,
                last_name=last_name,
                party=party,
                riding=riding,
                election=election,
                votetotal=votetotal,
                votepercent=votepercent,
                elected=None
            )

    election.label_winners()

PROVINCES_NORMALIZED = {
    'ab': 'AB',
    'alberta': 'AB',
    'bc': 'BC',
    'b.c.': 'BC',
    'british columbia': 'BC',
    'mb': 'MB',
    'manitoba': 'MB',
    'nb': 'NB',
    'new brunswick': 'NB',
    'nf': 'NL',
    'nl': 'NL',
    'newfoundland': 'NL',
    'newfoundland and labrador': 'NL',
    'nt': 'NT',
    'northwest territories': 'NT',
    'ns': 'NS',
    'nova scotia': 'NS',
    'nu': 'NU',
    'nunavut': 'NU',
    'on': 'ON',
    'ontario': 'ON',
    'pe': 'PE',
    'pei': 'PE',
    'p.e.i.': 'PE',
    'prince edward island': 'PE',
    'pq': 'QC',
    'qc': 'QC',
    'quebec': 'QC',
    'sk': 'SK',
    'saskatchewan': 'SK',
    'yk': 'YT',
    'yt': 'YT',
    'yukon': 'YT',
    'yukon territory': 'YT',
}        

def import_parl_election(url, election, session=None, soup=None): # FIXME session none only for now
    """Import an election from parl.gc.ca results.
    
    Sample URL: http://www2.parl.gc.ca/Sites/LOP/HFER/hfer.asp?Language=E&Search=Bres&ridProvince=0&genElection=0&byElection=2009%2F11%2F09&submit1=Search"""

    # Steps: 1. run this function
    # 2. el.label_winners()
    # 3. el.create_members(Session.objects.current())
    
    def _addParty(link):
        match = re.search(r'\?([^"]+)', link)
        if not match: raise Exception("Couldn't parse link in addParty")
        partyurl = 'http://www2.parl.gc.ca/Sites/LOP/HFER/hfer-party.asp?' + match.group(1)
        partypage = urllib2.urlopen(partyurl)
        partypage = re.sub(r'</?font[^>]*>', '', partypage.read()) # strip out font tags
        partysoup = BeautifulSoup(partypage, convertEntities='html')
        partyname = partysoup.find('td', width='85%').string.strip()
        if partyname:
            party = Party(name_en=partyname)
            party.save()
            return party
        else:
            raise Exception("Couldn't parse party name")
    
    page = urllib2.urlopen(url)
    page = re.sub(re.compile(r'</?font[^>]*>', re.I), '', page.read()) # strip out font tags
    if soup is None: soup = BeautifulSoup(page, convertEntities='html')
    
    # this works for elections but not byelections -- slightly diff format    
    #for row in soup.find('table', width="95%").findAll('tr'):
    
    for row in soup.find(text=re.compile('click on party abbreviation')).findNext('table').findAll('tr'):
      
        if row.find('h5'):
            # It's a province name
            province = row.find('h5').string
            province = PROVINCES_NORMALIZED[province.lower()]
            print "PROVINCE: %s" % province
            
        elif row.find('td', 'pro'):
            # It's a province name -- formatted differently on byelection pages
            provincetmp = row.find('b').string
            try:
                province = PROVINCES_NORMALIZED[provincetmp.lower()]
                print "PROVINCE: %s" % province
            except KeyError:
                # the 'province' class is sometimes used for non-province headings. thanks, parliament!
                print "NOT A PROVINCE: %s" % provincetmp

            
        elif row.find('td', 'rid'):
            # It's a riding name
            a = row.find('a')
            href = a['href']
            ridingname = a.string
            try:
                riding = Riding.objects.get_by_name(ridingname)
            except Riding.DoesNotExist:
                print "WARNING: Could not find riding %s" % ridingname
                riding = Riding(name=ridingname.strip().title(), province=province)
                riding.save()
            else:
                print "RIDING: %s" % riding
        
        elif row.find('td', bgcolor='#00224a'):
            # It's a heading
            pass
        elif row.find('td', align='right'):
            # It's a results row
            cells = row.findAll('td')
            if len(cells) != 6:
                raise Exception("Couldn't parse row: %s" % row)
                
            # Cell 2: party name
            link = cells[1].find('a')
            partylink = link['href']
            partyabbr = link.string
            try:
                party = Party.objects.get_by_name(partyabbr)
            except Party.DoesNotExist:
                party = _addParty(partylink)
                party.add_alternate_name(partyabbr)
                print "WARNING: Could not find party %s" % partyabbr
                
            # Cell 6: elected
            if cells[5].find('img'):
                elected = True
            else:
                elected = False
                
            # Cell 1: candidate name
            link = cells[0].find('a')
            if link:
                parllink = link['href']
                candidatename = link.string
            else:
                candidatename = cells[0].string.strip()
            (last, first) = candidatename.split(', ')
            last = last.strip().title()
            first = first.strip()
            
            # First, assemble a list of possible candidates
            candidate = None
            saveCandidate = False
            candidates = Politician.objects.filter_by_name("%s %s" % (first, last))
            # If there's nothing in the list, try a little harder
            if len(candidates) == 0:
                # Does the candidate have many given names?
                if first.strip().count(' ') >= 1:
                    minifirst = first.strip().split(' ')[0]
                    candidates = Politician.objects.filter_by_name("%s %s" % (minifirst, last))
            # Then, evaluate the possibilities in the list
            for posscand in candidates:
                # You're only a match if you've run for office for the same party in the same province
                match = ElectedMember.objects.filter(riding__province=riding.province, party=party, politician=posscand).count() >= 1 or Candidacy.objects.filter(riding__province=riding.province, party=party, candidate=posscand).count() >= 1
                if match:
                    if candidate is not None:
                        print "WARNING: Could not disambiguate existing candidates %s" % candidatename
                        candidate = None
                        break
                    else:
                        candidate = posscand
            if candidate is None:
                saveCandidate = True
                candidate = Politician(name="%s %s" % (first, last), name_given=first, name_family=last)
            
            # Cell 3: occupation
            occupation = cells[2].string
            
            # Cell 4: votes
            votetotal = parsetools.munge_int(cells[3].string)
            
            # Okay -- now see if this candidacy already exists
            candidacy = None
            if party.name != 'Independent':
                candidacies = Candidacy.objects.filter(election=election, riding=riding, party=party)
                if len(candidacies) > 1:
                    raise Exception("Too many candidacies!")
                elif len(candidacies) == 1:
                    candidacy = candidacies[0]
                    if candidate != candidacy.candidate:
                        print "WARNING: Forced riding/party match for candidate %s: %s" % (candidatename, candidacy.candidate)
                        candidate = candidacy.candidate
            if candidacy is None:
                candidacies = Candidacy.objects.filter(candidate=candidate, election=election)
                if len(candidacies) > 1:
                    raise Exception("Two candidacies for one candidate!")
                elif len(candidacies) == 1:
                    candidacy = candidacies[0]
                    if candidacy.riding != riding or candidacy.party != party:
                        print "WARNING: Invalid riding/party match for %s - %s (%s), %s (%s)" % (candidacy, riding, candidacy.riding == riding, party, candidacy.party == party)
                        continue
                else:
                    if saveCandidate: candidate.save()
                    candidacy = Candidacy(candidate=candidate, election=election, riding=riding, party=party)
            candidacy.occupation = unicode(occupation)
            candidacy.votetotal = votetotal
            candidacy.elected = elected
            candidacy.save()
            #print "%s (%s), a %s, got %d votes (elected: %s)" % (candidatename, partyabbr, occupation, votecount, elected)
    election.calculate_vote_percentages()
    
