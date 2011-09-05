import re
import urllib2

from BeautifulSoup import BeautifulSoup

from parliament.core.models import Politician, PoliticianInfo

def update_politician_info(pol):
    parlid = pol.info()['parl_id']
    url = 'http://webinfo.parl.gc.ca/MembersOfParliament/ProfileMP.aspx?Key=%s&Language=E' % parlid
    soup = BeautifulSoup(urllib2.urlopen(url))

    def _get_field(fieldname):
        return soup.find(id=re.compile(r'MasterPage_.+_DetailsContent_.+_' + fieldname + '$'))
    
    phonespan = _get_field('lblTelephoneData')
    if phonespan and phonespan.string:
        pol.set_info('phone', phonespan.string.replace('  ', ' '))
        
    faxspan = _get_field('lblFaxData')
    if faxspan and faxspan.string:
        pol.set_info('fax', faxspan.string.replace('  ', ' '))
        
    maillink = _get_field('hlEMail')
    if maillink and maillink.string:
        pol.set_info('email', maillink.string)
        
    weblink = _get_field('hlWebSite')
    if weblink and weblink['href']:
        pol.set_info('web_site', weblink['href'])
    
    constit_div = _get_field('divConstituencyOffices')
    if constit_div: 
        constit = u''
        for row in constit_div.findAll('td'):
            constit += unicode(row.string) if row.string else ''
            constit += "\n"
        pol.set_info('constituency_offices', constit.replace('Telephone:', 'Phone:'))