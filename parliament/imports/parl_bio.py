import urllib2

from BeautifulSoup import BeautifulSoup

from parliament.core.models import Politician, PoliticianInfo

def update_politician_info(pol):
    parlid = pol.info()['parl_id']
    url = 'http://webinfo.parl.gc.ca/MembersOfParliament/ProfileMP.aspx?Key=%s&Language=E' % parlid
    soup = BeautifulSoup(urllib2.urlopen(url))
    
    phonespan = soup.find(id='MasterPage_MasterPage_BodyContent_PageContent_Content_DetailsContent_DetailsContent__ctl0_lblTelephoneData')
    if phonespan and phonespan.string:
        pol.set_info('phone', phonespan.string.replace('  ', ' '))
        
    faxspan = soup.find(id='MasterPage_MasterPage_BodyContent_PageContent_Content_DetailsContent_DetailsContent__ctl0_lblFaxData')
    if faxspan and faxspan.string:
        pol.set_info('fax', faxspan.string.replace('  ', ' '))
        
    maillink = soup.find(id='MasterPage_MasterPage_BodyContent_PageContent_Content_DetailsContent_DetailsContent__ctl0_hlEMail')
    if maillink and maillink.string:
        pol.set_info('email', maillink.string)
        
    weblink = soup.find(id="MasterPage_MasterPage_BodyContent_PageContent_Content_DetailsContent_DetailsContent__ctl0_hlWebSite")
    if weblink and weblink['href']:
        pol.set_info('web_site', weblink['href'])
        
    constit = u''
    for row in soup.find(id='MasterPage_MasterPage_BodyContent_PageContent_Content_DetailsContent_DetailsContent__ctl0_divConstituencyOffices').findAll('td'):
        constit += unicode(row.string) if row.string else ''
        constit += "\n"
    if len(constit) > 500:
        print "TOO LONG %s" % constit
        constit = constit[:500]
    pol.set_info('constituency_offices', constit)