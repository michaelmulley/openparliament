import re
import urllib2

from BeautifulSoup import BeautifulSoup

from parliament.committees.models import Committee
from parliament.core.models import Session

COMMITEE_LIST_URL = 'http://www2.parl.gc.ca/CommitteeBusiness/CommitteeList.aspx?Language=E&Parl=%d&Ses=%d&Mode=2'
def import_committee_list(session=None):
    if session is None:
        session = Session.objects.current()
        
    ids_seen = set()
    
    def make_committee(namestring, parent=None):
        print namestring
        match = re.search(r'^(.+) \(([A-Z0-9]{4})\)$', namestring)
        (name, acronym) = match.groups()
        try:
            comm = Committee.objects.get(acronym=acronym, name=name)
        except Committee.DoesNotExist:
            comm = Committee(acronym=acronym, name=name)    
        comm.active = True
        comm.parent = parent
        comm.save()
        comm.sessions.add(session)
        ids_seen.add(comm.id)
        return comm
    
    soup = BeautifulSoup(urllib2.urlopen(COMMITEE_LIST_URL %
        (session.parliamentnum, session.sessnum)))
    for li in soup.findAll('li', 'CommitteeItem'):
        com = make_committee(li.find('a').string)
        for sub in li.findAll('li', 'SubCommitteeItem'):
            make_committee(sub.find('a').string, parent=com)
            
    Committee.objects.exclude(id__in=ids_seen).update(active=False)
    