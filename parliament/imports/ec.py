"""This is a half-finished module to import Elections Canada
contribution data.

It and parliament.financials were written in summer 2009
and haven't been touched since. Not that they're not worthwhile--they're
just looking for a home, and parents.
"""
import urllib, urllib2
from xml.etree.ElementTree import ElementTree
import re, datetime
import decimal

from BeautifulSoup import BeautifulSoup
from django.db import transaction

from parliament.core import parsetools
from parliament.core.models import *

AGENT_HEADER = {
    'User-Agent' : 'Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10.5; en-US; rv:1.9.1.2) Gecko/20090729 Firefox/3.5.2',
}

POST_indivcontrib = {
"PrevReturn":0,
"contribclass":	12,
"contribed":	-1,
"contribfiscalfrom":	0,
"contribfiscalto":	0,
"contribname":	'',
"contribpp":	-1,
"contribprov":	-1,
"contribrange":	-1,
"entity":	1,
"filter":	31,
"id":	'',
"ids":	'',
"lang":	'e',
"option":	4,
"page":	1,
"part":	'',
"period":	-1,
"return":	1,
"searchentity":	0,
"sort":	0,
"style":	0,
"table": '',
}
URL_indivcontrib = 'http://www.elections.ca/scripts/webpep/fin2/detail_report.aspx'

def tmp_contribsoup():
    postdata = urllib.urlencode(POST_indivcontrib)
    request = urllib2.Request(URL_indivcontrib, postdata)
    response = urllib2.urlopen(request)
    return BeautifulSoup(response)

    def ec_indivContribRunner(election):

        while (True):
            postdata = urllib.urlencode(POST_indivcontrib)
            request = urllib2.Request(URL_indivcontrib, postdata, AGENT_HEADER)
            print "Requesting page %d... " % POST_indivcontrib['page'],
            response = urllib2.urlopen(request)
            soup = BeautifulSoup(response)
            print "done."
            ec_indivContribPage(soup, election)
            print "Checking for next link... ",
            if soup.find('a', href='javascript:ShowPage(-1);'):
                print "found!"
                POST_indivcontrib['page'] += 1
            else:
                print "not found -- complete!"
                break

    @transaction.commit_on_success
    def ec_indivContribPage(soup, election):
        """ Parses a page of Elections Canada's individual contributions to candidates > $200 list. """

        CONTRIB_URL = 'http://www.elections.ca/scripts/webpep/fin2/contributor.aspx'

        def create_politician(first, last):
            pol = Politician(name_given=first, name_family=last, name="%s %s" % (first, last))
            pol.save()
            return pol

        def get_contributor(href, name):
            """ The Elections Canada page provides postal codes only a separate popup
            window -- so, for each contributor, we have to fetch it."""
            match = re.search(r"contributor.aspx(\?[^']+)'", href)
            if not match:
                raise Exception("Couldn't parse link %s" % href)
            if not name:
                raise Exception("Invalid name %s" % name)
            pname = name.title()
            url = CONTRIB_URL + re.sub(r'&amp;', '&', match.group(1))
            req = urllib2.Request(url, headers=AGENT_HEADER)
            response = urllib2.urlopen(req)
            contribsoup = BeautifulSoup(response)
            (city, province, postcode) = (contribsoup.find('span', id='lblCity').string, contribsoup.find('span', id='lblProvince').string, parsetools.munge_postcode(contribsoup.find('span', id='lblPostalCode').string))
            if postcode:
                try:
                    contrib = Contributor.objects.get(name=pname, postcode=postcode)
                except Contributor.DoesNotExist:
                    pass
                else:
                    return contrib
            contrib = Contributor(name=pname, city=city, postcode=postcode, province=province)
            contrib.save()
            return contrib

        mainTable = soup.find('table', rules='all')
        for row in mainTable.findAll('tr', attrs={'class' : ['odd_row', 'even_row']}):
            cells = row.findAll('td')
            if len(cells) != 7:
                raise Exception('Wrong number of cells in %s' % row)

            # Get the contribution amount 
            amount_mon = parsetools.munge_decimal(cells[5].string)
            amount_non = parsetools.munge_decimal(cells[6].string)
            amount = amount_mon + amount_non
            if amount == 0:
                print "WARNING: Zero amount -- %s and %s" % (cells[5].string, cells[6].string)
                continue

            # Is there a date?
            if len(cells[2].string) > 6:
                try:
                    if cells[2].string.count('.') > 0:
                        date = datetime.datetime.strptime(cells[2].string, '%b. %d, %Y')
                    else:
                        date = datetime.datetime.strptime(cells[2].string, '%b %d, %Y')                    
                except ValueError:
                    print "WARNING: Unparsable date %s" % cells[2].string
                    date = None
            else:
                date = None

            # Who's the contribution to?
            # This is the unfortunately-long part
            recipient = cells[1].string.split(' / ')
            if len(recipient) != 3:
                print "WARNING: Unparsable recipient: %s" % cells[1].string
                continue
            (cname, partyname, ridingname) = recipient

            # First, get the recipient's name
            cname = cname.split(', ')
            if len(cname) != 2:
                print "WARNING: Couldn't parse candidate name %s" % recipient[0]
                continue
            (last, first) = cname

            # Get the recipient's riding
            try:
                riding = Riding.objects.get(name=ridingname)
            except Riding.DoesNotExist:
                print "WARNING: Riding not found: %s" % ridingname
                continue

            # Get the recipient's party    
            try:
                party = Party.objects.get(name=partyname)
            except Party.DoesNotExist:
                print "CREATING party: %s" % partyname
                party = Party(name=partyname)
                party.save()

            # With all this info, we can get a Candidacy object
            try:
                if partyname == 'Independent':
                    # Independent is the only 'party' where two candidates might be running in the same riding & election
                    candidacy = Candidacy.objects.get(riding=riding, party=party, election=election, candidate__name_family=last)
                else:
                    candidacy = Candidacy.objects.get(riding=riding, party=party, election=election)
            except Candidacy.DoesNotExist:
                # No candidacy -- let's create one
                # Let's see if this person already exists
                try:
                    pol = Politician.objects.get(name_given=first, name_family=last)
                except Politician.DoesNotExist:
                    pol = create_politician(first, last)
                except Politician.MultipleObjectsReturned:
                    # ah, similar names
                    # FIXME: after importing this first election, this should search candidacies as well as successful elections
                    possiblepols = Politician.objects.filter(name_given=first, name_family=last, electedmember__party=party)
                    if len(possiblepols) == 1:
                        pol = possiblepols[0]
                    elif len(possiblepols) > 1:
                        # Two people, with the same name, elected from the same party!
                        print "WARNING: Can't disambiguate politician %s" % recipient[0]
                        continue
                    else:
                        # let's create a new one for now
                        pol = create_politician(first, last)

                candidacy = Candidacy(riding=riding, party=party, election=election, candidate=pol)
                candidacy.save()
            else:
                pol = candidacy.candidate
                if pol.name != "%s %s" % (first, last):
                    # FIXME doesn't handle independents properly
                    print "WARNING: Politician names don't match: %s and %s %s" % (pol.name, first, last)

            # Finally, the contributor!
            if cells[0].contents[0].name != 'a':
                print "WARNING: Can't parse contributor"
                continue
            contriblink = cells[0].contents[0]
            try:
                contributor = get_contributor(contriblink['href'], contriblink.string)
            except Exception, e:
                print "WARNING: Error getting contributor: %s" % e
                continue

            # WE HAVE EVERYTHING!!!
            Contribution(contributor=contributor, amount=amount, amount_monetary=amount_mon, amount_nonmonetary=amount_non, date=date, individual_recipient=candidacy).save()
        return True
