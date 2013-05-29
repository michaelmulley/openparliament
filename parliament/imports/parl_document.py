"""Parse XML transcripts from parl.gc.ca.

These transcripts are either House Hansards, or House committee evidence.

Most of the heavily-lifting code has been put in a separate module
called alpheus: http://github.com/rhymeswithcycle/alpheus
"""
from difflib import SequenceMatcher
import re
import sys
import urllib2
from xml.sax.saxutils import quoteattr

from django.core import urlresolvers
from django.db import transaction

import alpheus
from BeautifulSoup import BeautifulSoup

from parliament.bills.models import Bill, BillInSession, VoteQuestion
from parliament.core.models import Politician, ElectedMember, Session
from parliament.hansards.models import Statement, Document, OldSequenceMapping

import logging
logger = logging.getLogger(__name__)

@transaction.commit_on_success
def import_document(document, interactive=True, reimport_preserving_sequence=False):
    old_statements = None
    if document.statement_set.all().exists():
        if reimport_preserving_sequence:
            if OldSequenceMapping.objects.filter(document=document).exists():
                logger.error("Sequence mapping already exits for %s" % document)
                return
            old_statements = list(document.statement_set.all())
            document.statement_set.all().delete()
        else:
            if not interactive:
                return
            sys.stderr.write("Statements already exist for %r.\nDelete them? (y/n) " % document)
            if raw_input().strip() != 'y':
                return
            document.statement_set.all().delete()

    document.download()
    xml_en = document.get_cached_xml('en')
    pdoc_en = alpheus.parse_file(xml_en)
    xml_en.close()

    xml_fr = document.get_cached_xml('fr')
    pdoc_fr = alpheus.parse_file(xml_fr)
    xml_fr.close()
    
    if document.date and document.date != pdoc_en.meta['date']:
        # Sometimes they get the date wrong
        if document.date != pdoc_fr.meta['date']:
            logger.error("Date mismatch on document #%s: %s %s" % (
                document.id, document.date, pdoc_en.meta['date']))
    else:
        document.date = pdoc_en.meta['date']
    document.number = pdoc_en.meta['document_number']
    document.public = True

    statements = []

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

        if s.h3 and not s.h2:
            s.h2 = s.h3
            s.h3 = ''

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
                logger.info("Could not resolve speaking politician ID %s for %r" % (s.who_hocid, s.who))

        s._related_pols = set()
        s._related_bills = set()
        s.content_en = _process_related_links(s.content_en, s)

        statements.append(s)

    if len(statements) != len(pdoc_fr.statements):
        logger.info("French and English statement counts don't match for %r" % document)

    fr_statements = dict((getattr(s, 'meta', dict()).get('id', None), s) for s in pdoc_fr.statements)
    if None in fr_statements:
        del fr_statements[None]
    _r_paragraphs = re.compile(ur'<p[^>]* data-HoCid=.+?</p>')
    _r_paragraph_id = re.compile(ur'<p[^>]* data-HoCid="(?P<id>\d+)"')
    fr_paragraphs = dict()

    def _get_paragraph_id(p):
        return int(_r_paragraph_id.match(p).group('id'))

    for st in pdoc_fr.statements:
        for p in _r_paragraphs.findall(st.content):
            fr_paragraphs[_get_paragraph_id(p)] = p

    def _substitute_french_content(match):
        try:
            return fr_paragraphs[_get_paragraph_id(match.group(0))]
        except KeyError:
            logger.error("Paragraph ID %s not found in French for %s" % (match.group(0), document))
            return match.group(0)

    for st in statements:
        st.content_fr = _process_related_links(
            _r_paragraphs.sub(_substitute_french_content, st.content_en),
            st
        )
        for heading in range(1, 4):
            fr_meta = getattr(fr_statements.get(st.source_id, None), 'meta', dict())
            setattr(st, 'h%s_fr' % heading, fr_meta.get('h%s' % heading, ''))
    document.multilingual = True

    Statement.set_slugs(statements)

    if old_statements:
        for mapping in _align_sequences(statements, old_statements):
            OldSequenceMapping.objects.create(
                document=document,
                sequence=mapping[0],
                slug=mapping[1]
            )
        
    for s in statements:
        s.save()

        s.mentioned_politicians.add(*list(s._related_pols))
        s.bills.add(*list(s._related_bills))
        if getattr(s, '_related_vote', False):
            s._related_vote.context_statement = s
            s._related_vote.save()

    document.save()

    return document

def _align_sequences(new_statements, old_statements):
    """Given two list of statements, returns a list of mappings in the form of
    (old_statement_sequence, new_statement_slug)"""

    def build_speaker_dict(states):
        d = {}
        for s in states:
            d.setdefault(s.name_info['display_name'], []).append(s)
        return d

    def get_comparison_sequence(text):
        return re.split(r'\s+', text)

    def calculate_similarity(old, new):
        """Given two statements, return a score between 0 and 1 expressing their similarity"""
        score = 0.8 if old.time == new.time else 0.0
        oldtext, newtext = old.text_plain(), new.text_plain()
        if new in chosen:
            score -= 0.01
        if newtext in oldtext:
            similarity = 1.0
        else:
            similarity = SequenceMatcher(
                None, get_comparison_sequence(oldtext), get_comparison_sequence(newtext)
            ).ratio()
        return (score + similarity) / 1.8

    new_speakers, old_speakers = build_speaker_dict(new_statements), build_speaker_dict(old_statements)
    mappings = []
    chosen = set()

    for speaker, olds in old_speakers.items():
        news = new_speakers.get(speaker, [])
        if speaker and len(olds) == len(news):
            # The easy version: assume we've got the same statements
            for old, new in zip(olds, news):
                score = calculate_similarity(old, new)
                if score < 0.9:
                    logger.warning("Low similarity for easy match %s: %r %r / %r %r"
                        % (score, old, old.text_plain(), new, new.text_plain()))
                mappings.append((old.sequence, new.slug))
        else:
            # Try and pair the most similar statement
            if news:
                logger.info("Count mismatch for %s" % speaker)
                candidates = news
            else:
                logger.warning("No new statements for %s" % speaker)
                candidates = new_statements # Calculate similarity with all possibilities
            for old in olds:
                scores = ( (cand, calculate_similarity(old, cand)) for cand in candidates )
                choice, score = max(scores, key=lambda s: s[1])
                chosen.add(choice)
                if score < 0.75:
                    logger.warning("Low-score similarity match %s: %r %r / %r %r"
                        % (score, old, old.text_plain(), choice, choice.text_plain()))
                mappings.append((old.sequence, choice.slug))

    return mappings

def _process_related_links(content, statement):
    return re.sub(r'<a class="related_link (\w+)" ([^>]+)>(.*?)</a>',
        lambda m: _process_related_link(m, statement),
        content)

def _process_related_link(match, statement):
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
        statement._related_pols.add(pol)
    elif link_type == 'legislation':
        try:
            bis = BillInSession.objects.get_by_legisinfo_id(hocid)
            bill = bis.bill
            url = bis.get_absolute_url()
        except Bill.DoesNotExist:
            match = re.search(r'\b[CS]\-\d+[A-E]?\b', text)
            if not match:
                logger.error("Invalid bill link %s" % text)
                return text
            bill = Bill.objects.create_temporary_bill(legisinfo_id=hocid,
                number=match.group(0), session=statement.document.session)
            url = bill.get_absolute_url()
        title = bill.name
        statement._related_bills.add(bill)
    elif link_type == 'vote':
        try:
            vote = VoteQuestion.objects.get(session=statement.document.session,
                number=int(params['number']))
            url = vote.get_absolute_url()
            title = vote.description
            statement._related_vote = vote
        except VoteQuestion.DoesNotExist:
            # We'll just operate on faith that the vote will soon
            # be created
            url = urlresolvers.reverse('parliament.bills.views.vote',
                kwargs={'session_id': statement.document.session_id, 'number': params['number']})
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




        

