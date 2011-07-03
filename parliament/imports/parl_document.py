"""Parse XML transcripts from parl.gc.ca.

These transcripts are either House Hansards, or House committee evidence.

Most of the heavily-lifting code has been put in a separate module
called alpheus: http://github.com/rhymeswithcycle/alpheus
"""
import re
import sys
import urllib2
from xml.sax.saxutils import quoteattr

from django.core import urlresolvers
from django.db import transaction

import alpheus
from BeautifulSoup import BeautifulSoup

from parliament.bills.models import Bill, VoteQuestion
from parliament.core.models import Politician, ElectedMember, Session
from parliament.hansards.models import Statement, Document

import logging
logger = logging.getLogger(__name__)

@transaction.commit_on_success
def import_document(document, interactive=True):
    if document.statement_set.all().exists():
        if interactive:
            sys.stderr.write("Statements already exist for %r.\nDelete them? (y/n) " % document)
            yn = raw_input()
            if yn.strip() == 'y':
                document.statement_set.all().delete()
            else:
                return
        else:
            return

    document.download()
    xml_en = document.get_cached_xml('en')
    pdoc_en = alpheus.parse_file(xml_en)
    xml_en.close()

    xml_fr = document.get_cached_xml('fr')
    pdoc_fr = alpheus.parse_file(xml_fr)
    xml_fr.close()

    if len(pdoc_en.statements) != len(pdoc_fr.statements):
        raise Exception("French and English statement counts don't match for %r" % document)

    document.date = pdoc_en.meta['date']
    document.number = pdoc_en.meta['document_number']
    document.save()

    statements = []

    def _process_related_links(content):
        return re.sub(r'<a class="related_link (\w+)" ([^>]+)>(.+?)</a>', _process_related_link, content)

    def _process_related_link(match):
        (link_type, tagattrs, text) = match.groups()
        params = dict([(m.group(1), m.group(2)) for m in re.finditer(r'data-([\w-]+)="([^"]+)"', tagattrs)])
        hocid = int(params['HoCid'])
        if link_type == 'politician':
            try:
                pol = Politician.objects.get_by_parl_id(hocid)
            except Politician.DoesNotExist:
                logger.error("Could not resolve related politician #%s, %r" % (hocid, text))
                return text
            url = pol.get_absolute_url()
            title = pol.name
            s._related_pols.add(pol)
        elif link_type == 'legislation':
            try:
                bill = Bill.objects.get_by_legisinfo_id(hocid)
            except Bill.DoesNotExist:
                match = re.search(r'\b[CS]\-\d+[A-E]?\b', text)
                if not match:
                    logger.error("Invalid bill link %s" % text)
                    return text
                bill = Bill.objects.create_temporary_bill(legisinfo_id=hocid,
                    number=match.group(0), session=document.session)
            url = bill.get_absolute_url()
            title = bill.name
            s._related_bills.add(bill)
        elif link_type == 'vote':
            try:
                vote = VoteQuestion.objects.get(session=document.session,
                    number=int(params['number']))
                url = vote.get_absolute_url()
                title = vote.description
                s._related_vote = vote
            except VoteQuestion.DoesNotExist:
                # We'll just operate on faith that the vote will soon
                # be created
                url = urlresolvers.reverse('parliament.bills.views.vote',
                    kwargs={'session_id': document.session_id, 'number': params['number']})
                title = None
        else:
            raise Exception("Unknown link type %s" % link_type)

        attrs = {
            'href': url,
            'data-HoCid': hocid
        }
        if title:
            attrs['title'] = title
        return _build_tag(u'a', attrs) + text + u'</a>'
            

    for pstate in pdoc_en.statements:
        s = Statement(
            document=document,
            sequence=len(statements),
            content_en=pstate.content,
            time=pstate.meta['timestamp'])
        s.source_id = pstate.meta['id']
        s.h1 = pstate.meta.get('h1', '')
        s.h2 = pstate.meta.get('h2', '')
        s.h3 = pstate.meta.get('h3', '')

        s.who = pstate.meta.get('person_attribution', '')
        s.who_hocid = int(pstate.meta['person_id']) if pstate.meta.get('person_id') else None
        s.who_context = pstate.meta.get('person_context', '')

        s.statement_type = pstate.meta.get('intervention_type', '').lower()
        s.written_question = pstate.meta.get('written_question', '').upper()[:1]

        if s.who_hocid and not pstate.meta.get('person_type'):
            # At the moment. person_type is only set if we know the person
            # is a non-politician. This might change...
            try:
                s.politician = Politician.objects.get_by_parl_id(s.who_hocid, session=document.session)
                s.member = ElectedMember.objects.get_by_pol(s.politician, date=document.date)
            except Politician.DoesNotExist:
                logger.error("Could not resolve speaking politician ID %s for %r" % (s.who_hocid, s.who))

        s._related_pols = set()
        s._related_bills = set()
        s.content_en = _process_related_links(s.content_en)

        statements.append(s)

    assert len(statements) == len(pdoc_fr.statements)
    for s, pstate in zip(statements, pdoc_fr.statements):
        if s.source_id != pstate.meta['id']:
            raise Exception("Statement IDs do not match in en/fr. %s %s" % (s.source_id, pstate.meta['id']))

        s.content_fr = _process_related_links(pstate.content)
        s.save()

        s.mentioned_politicians.add(*list(s._related_pols))
        s.bills.add(*list(s._related_bills))
        if getattr(s, '_related_vote', False):
            s._related_vote.context_statement = s
            s._related_vote.save()

    return document


def _build_tag(name, attrs):
    return u'<%s%s>' % (
        name,
        u''.join([u" %s=%s" % (k, quoteattr(unicode(v))) for k,v in sorted(attrs.items())])
    )

def _docid_from_url(u):
    return int(re.search(r'DocId=(\d+)', u).group(1))

def fetch_latest_debates(session=None):
    if not session:
        session = Session.objects.current()

    url = 'http://www2.parl.gc.ca/housechamberbusiness/chambersittings.aspx?View=H&Parl=%d&Ses=%d&Language=E&Mode=2' % (
        session.parliamentnum, session.sessnum)
    soup = BeautifulSoup(urllib2.urlopen(url))

    cal = soup.find('div', id='ctl00_PageContent_calTextCalendar')
    for link in cal.findAll('a', href=True):
        source_id = _docid_from_url(link['href'])
        if not Document.objects.filter(source_id=source_id).exists():
            Document.objects.create(
                document_type=Document.DEBATE,
                session=session,
                source_id=source_id
            )




        

