"""Parse XML transcripts from ourcommons.ca.

These transcripts are either House Hansards, or House committee evidence.

Most of the heavily-lifting code has been put in a separate module
called alpheus.
"""
from collections.abc import Iterable
import datetime
import difflib
import re
import sys
from xml.sax.saxutils import quoteattr

from django.urls import reverse
from django.db import transaction, models

from lxml import etree
import requests

from parliament.bills.models import Bill, VoteQuestion
from parliament.core.models import Politician, ElectedMember, Session
from parliament.hansards.models import Statement, Document, OldSlugMapping
from . import alpheus
from .legisinfo import OldBillException

import logging
logger = logging.getLogger(__name__)

class ReimportException(Exception):
    pass

@transaction.atomic
def import_document(document: Document, allow_reimport=True, prompt_on_slug_change=False,
                    xml_en: bytes | None = None, xml_fr: bytes | None = None):
    old_statements = was_multilingual = None
    if document.statement_set.all().exists():
        if not allow_reimport:
            raise Exception("Statements already exist for %r and allow_reimport is False" % document)
        old_statements = list(document.statement_set.all())
        was_multilingual = document.multilingual
    
    if not xml_en:
        xml_en = document.get_cached_xml('en')
    pdoc_en = alpheus.parse_bytes(xml_en)
    if not xml_fr:
        xml_fr = document.get_cached_xml('fr')
    pdoc_fr = alpheus.parse_bytes(xml_fr)
    
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
        s.h1_en = pstate.meta.get('h1', '')
        s.h2_en = pstate.meta.get('h2', '')
        s.h3_en = pstate.meta.get('h3', '')

        if s.h1_en and not s.h2_en:
            s.h2_en = s.h3_en
            s.h3_en = ''

        s.who_en = pstate.meta.get('person_attribution', '')[:300]
        try:
            s.who_hocid = int(pstate.meta['person_id']) if pstate.meta.get('person_id') else None
        except ValueError:
            logger.warning("ValueError parsing person ID %s", pstate.meta['person_id'])
            s.who_hocid = None
        s.who_context_en = pstate.meta.get('person_context', '')[:300]

        s.statement_type = pstate.meta.get('intervention_type', '').lower()
        s.written_question = pstate.meta.get('written_question', '').upper()[:1]

        if s.who_hocid and not pstate.meta.get('person_type'):
            # At the moment. person_type is only set if we know the person
            # is a non-politician. This might change...
            try:
                s.politician = Politician.objects.get_by_parl_affil_id(s.who_hocid, session=document.session)
                s.member = ElectedMember.objects.get_by_pol(s.politician, date=document.date)
            except Politician.DoesNotExist:
                logger.info("Could not resolve speaking politician ID %s for %r" % (s.who_hocid, s.who))

        s._mentioned_pols = set()
        s._mentioned_bills = set()
        s.content_en = _process_related_links(s.content_en, s)

        if pstate.meta.get('bill_stage'):
            bill_number, stage = pstate.meta['bill_stage'].split(',', maxsplit=1)
            s.bill_debated = Bill.objects.get(number=bill_number, session=document.session)
            if stage in ['1', '2', '3', 'report', 'senate']:
                s.bill_debate_stage = stage
            else:
                s.bill_debate_stage = 'other'

        statements.append(s)

    _incorporate_french_document(document, statements, pdoc_fr)

    if old_statements:
        if was_multilingual and not document.multilingual:
            raise ReimportException("Document was multilingual but now isn't")
        _assign_slugs_on_reimport(
            document, statements, old_statements, prompt_on_slug_change)
        document.statement_set.all().delete()
    else:
        Statement.set_slugs(statements)
        
    for s in statements:
        s.save()

        s.mentioned_politicians.add(*list(s._mentioned_pols))
        s.mentioned_bills.add(*[b for b in s._mentioned_bills if b != s.bill_debated])
        if getattr(s, '_related_vote', False):
            s._related_vote.context_statement = s
            s._related_vote.save()

    bills_debated = set(s.bill_debated for s in statements 
                        if s.bill_debated and s.bill_debate_stage not in ('other', '1'))
    for bill in bills_debated:
        if bill.latest_debate_date is None or bill.latest_debate_date < document.date:
            bill.latest_debate_date = document.date
            bill.save()

    document.last_imported = datetime.datetime.now()
    if not (old_statements or document.first_imported):
        document.first_imported = document.last_imported
    document.save()

    return document

def _incorporate_french_document(document: Document, statements: list[Statement],
                                 pdoc_fr: alpheus.AlpheusDocument) -> None:
    """Given an Alpheus import of a French XML document, adds French metadata
    and text to the existing Statement objects (derived from the English import)."""
    if len(statements) != len(pdoc_fr.statements):
        logger.info("French and English statement counts don't match for %r" % document)

    fr_paragraphs = dict()
    fr_statements = dict()
    missing_id_count = 0

    for st in pdoc_fr.statements:
        if st.meta['id']:
            fr_statements[st.meta['id']] = st
        for p, pid in _get_paragraphs_and_ids(st.content):
            if pid:
                fr_paragraphs[pid] = p
            else:
                missing_id_count += 1

    def _substitute_french_content(match):
        try:
            pid = _get_paragraph_id(match.group(0))
            if pid:
                return fr_paragraphs[pid]
            else:
                return match.group(0)
        except KeyError:
            logger.error("Paragraph ID %s not found in French for %s" % (match.group(0), document))
            return match.group(0)

    if missing_id_count > float(len(fr_paragraphs)):
        logger.error("French paragraphs not available")
        document.multilingual = False
    else:
        document.multilingual = True
        for st in statements:
            fr_data = fr_statements.get(st.source_id)
            pids_en = [pid for p, pid in _get_paragraphs_and_ids(st.content_en)]
            pids_fr = [pid for p, pid in _get_paragraphs_and_ids(fr_data.content)] if fr_data else None
            if fr_data and pids_en == pids_fr:
                # Match by statement
                st.content_fr = _process_related_links(fr_data.content, st)
            elif all(pids_en):
                # Match by paragraph
                st.content_fr = _process_related_links(
                    _r_paragraphs.sub(_substitute_french_content, st.content_en),
                    st
                )
            else:
                logger.warning("Could not do multilingual match of statement %s", st.source_id)
                document.multilingual = False
            if fr_data:
                st.h1_fr = fr_data.meta.get('h1', '')
                st.h2_fr = fr_data.meta.get('h2', '')
                st.h3_fr = fr_data.meta.get('h3', '')
                if st.h1_fr and not st.h2_fr:
                    st.h2_fr = st.h3_fr
                    st.h3_fr = ''
                st.who_fr = fr_data.meta.get('person_attribution', '')[:300]
                st.who_context_fr = fr_data.meta.get('person_context', '')[:300]

def _assign_slugs_on_reimport(document: Document, statements: list[Statement],
                              old_statements: list[Statement], prompt_on_slug_change: bool) -> None:
    """When reimporting, if there are now a different number of statements by a given person,
    we want to ensure that existing links that used a statement slug remained valid.
    
    This function assign slugs to all statements in `statements`, keeping in mind the previous
    slugs from `old_statements`. If necessary, OldSlugMapping objects are saved to keep existing links working."""
    old_slugs = set(s.slug for s in old_statements)
    
    # Check if we already had, from a previous reimport, slugs in the form of joe-blow-a
    initial_slug_substitutions = dict()
    for s in old_slugs:
        match = re.search(r'^(.+)(-[a-z])(-\d+)$', s)
        if match:
            initial_slug_substitutions.setdefault(match.group(1), match.group(1) + match.group(2))
            if initial_slug_substitutions[match.group(1)] != match.group(1) + match.group(2):
                raise ReimportException(f"Processing slug {s}, found existing conflicting substition: {initial_slug_substitutions[match.group(1)]}")
    Statement.set_slugs(statements, substitute_names=initial_slug_substitutions)

    new_slugs = set(s.slug for s in statements)
    if old_slugs != new_slugs:
        logger.warning("Statement slugs changed for %r: %r",
                        document, old_slugs.symmetric_difference(new_slugs))
        new_slug_names = initial_slug_substitutions.copy()
        changed_slug_names = set(re.sub(r'-\d+$', '', s) for s in 
                                    _map_changed_slugs(old_statements, statements).keys())
        for n in changed_slug_names:
            if re.search(r'-[a-z]$', n):
                # joe-blow-a -> joe-blow-b
                # joe-blow -> joe-blow-b
                new_slug_names[n] = re.sub(r'-[a-z]$', lambda match: '-' + chr(ord(match.group()[-1]) + 1), n)
                new_slug_names[re.sub(r'-[a-z]$', '', n)] = new_slug_names[n]
            else:
                # joe-blow -> joe-blow-a
                new_slug_names[n] = n + '-a'
        Statement.set_slugs(statements, substitute_names=new_slug_names)
        slugmap = _map_changed_slugs(old_statements, statements)            
        print(slugmap)
        if not slugmap.keys().isdisjoint(slugmap.values()):
            raise Exception("Overlap between old and new slugs in map_changed_slugs: %r" % slugmap)            
        if prompt_on_slug_change:
            sys.stderr.write("Delete and reimport anyway? (y/n) ")
            if input().strip() != 'y':
                raise ReimportException("Not reimporting %r because statement slugs changed" % document)
        for old_slug, new_slug in slugmap.items():
            OldSlugMapping(document=document, old_slug=old_slug, new_slug=new_slug).save()

_r_paragraphs = re.compile(r'<p[^>]* data-HoCid=.+?</p>')
_r_paragraph_id = re.compile(r'<p[^>]* data-HoCid="(?P<id>\d+)"')

def _get_paragraph_id(p: str) -> int:
    return int(_r_paragraph_id.match(p).group('id'))

def _get_paragraphs_and_ids(content: str) -> list[tuple[str, int]]:
    return [(p, _get_paragraph_id(p)) for p in _r_paragraphs.findall(content)]

def _map_changed_slugs(old_st: list[Statement], new_st: list[Statement]) -> dict[str, str]:
    new_p_ids = dict()
    for s in new_st:
        for _, pid in _get_paragraphs_and_ids(s.content_en):
            if pid:
                new_p_ids[pid] = s
    
    slugmap = dict()
    for s in old_st:
        for _, pid in _get_paragraphs_and_ids(s.content_en):
            if pid in new_p_ids:
                if s.slug != new_p_ids[pid].slug:
                    slugmap[s.slug] = new_p_ids[pid].slug
                break
    return slugmap

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
            pol = Politician.objects.get_by_parl_affil_id(hocid)
        except Politician.DoesNotExist:
            logger.warning("Could not resolve related politician #%s, %s", hocid, text)
            return text
        url = pol.get_absolute_url()
        title = pol.name
        statement._mentioned_pols.add(pol)
    elif link_type == 'legislation':
        try:
            bill = Bill.objects.get_by_legisinfo_id(hocid)
            url = bill.get_absolute_url()
        except Bill.DoesNotExist:
            match = re.search(r'\b[CS]\-\d+[A-E]?\b', text)
            if not match:
                logger.error("Invalid bill link %s" % text)
                return text
            bill = Bill.objects.create_temporary_bill(legisinfo_id=hocid,
                number=match.group(0), session=statement.document.session)
            url = bill.get_absolute_url()
        except OldBillException:
            logger.info(f"Old bill, not importing: #{hocid} {text}")
            return text
        title = bill.name
        statement._mentioned_bills.add(bill)
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
            url = reverse('vote',
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
    return _build_tag('a', attrs) + text + '</a>'

def _build_tag(name, attrs):
    return '<%s%s>' % (
        name,
        ''.join([" %s=%s" % (k, quoteattr(str(v))) for k,v in sorted(attrs.items())])
    )

def _test_has_paragraph_ids(elem):
    """Do all, or almost all, of the paragraphs in this document have ID attributes? 
    Sometimes they're missing at first."""
    paratext = elem.xpath('//ParaText')
    paratext_with_id = [pt for pt in paratext if pt.get('id')]
    return (len(paratext_with_id) / float(len(paratext))) > 0.95

HANSARD_URL = 'https://www.ourcommons.ca/Content/House/{parliamentnum}{sessnum}/Debates/{sitting:03d}/HAN{sitting:03d}-{lang}.XML'

class NoDocumentFound(Exception):
    pass

def fetch_latest_debates(session=None):
    if not session:
        session = Session.objects.current()

    sittings = Document.objects.filter(
        document_type=Document.DEBATE, session=session).values_list(
        'number', flat=True)
    # FIXME at the moment ourcommons.ca doesn't make it easy to get a list of
    # debates; this is a quick temporary solution that will break on special
    # sittings like 128-B
    if len(sittings) == 0:
        max_sitting = 0
    else:
        max_sitting = max(int(n) for n in sittings if n.isdigit())

    while True:
        max_sitting += 1
        try:
            fetch_debate_for_sitting(session, max_sitting)
        except NoDocumentFound:
            break


def fetch_debate_for_sitting(session, sitting_number, import_without_paragraph_ids=True):
    url_en = HANSARD_URL.format(parliamentnum=session.parliamentnum,
        sessnum=session.sessnum, sitting=sitting_number, lang='E')
    resp = requests.get(url_en)
    if resp.status_code != 200:
        if resp.status_code != 404:
            logger.error("Response %d from %s", resp.status_code, url_en)
        raise NoDocumentFound
    print(url_en)
    xml_en = resp.content.replace(b'\r\n', b'\n')

    url_fr = HANSARD_URL.format(parliamentnum=session.parliamentnum,
        sessnum=session.sessnum, sitting=sitting_number, lang='F')
    resp = requests.get(url_fr)
    resp.raise_for_status()
    xml_fr = resp.content.replace(b'\r\n', b'\n')

    doc_en = etree.fromstring(xml_en)
    doc_fr = etree.fromstring(xml_fr)

    source_id = int(doc_en.get('id'))
    if Document.objects.filter(source_id=source_id).exists():
        raise Exception("Document at source_id %s already exists but not sitting %s" %
            (source_id, sitting_number))
    assert int(doc_fr.get('id')) == source_id

    if ((not import_without_paragraph_ids) and
            not (_test_has_paragraph_ids(doc_en) and _test_has_paragraph_ids(doc_fr))):
        logger.warning("Missing paragraph IDs, cancelling")
        return

    with transaction.atomic():
        doc = Document.objects.create(
            document_type=Document.DEBATE,
            session=session,
            source_id=source_id,
            number=str(sitting_number)
        )
        doc.save_xml(url_en, xml_en, xml_fr)
        logger.info("Saved sitting %s", doc.number)

def _remove_whitespace(text: str) -> str:
    return re.sub(r'\s+', '', text)

def format_xml(xml_string: bytes) -> bytes:
    # Pretty-prints an XML bytestring
    return etree.tostring(
        etree.fromstring(xml_string, etree.XMLParser(remove_blank_text=True)),
        pretty_print=True, encoding='utf8', xml_declaration=True)     

def check_for_xml_updates(document: Document, print_diff=True,
                        reimport=False, prompt_on_slug_change=False, prompt_to_import=False):
    assert document.downloaded
    result = {}
    xml_bytes = {}
    xml_urls = {}

    for lang in ('en', 'fr'):
        url = xml_urls[lang] = document.get_xml_url(lang)
        resp = requests.get(url)
        resp.raise_for_status()
        xml_bytes[lang] = resp.content.replace(b'\r\n', b'\n')
        new_xml = format_xml(xml_bytes[lang]).decode('utf8')
        old_xml = format_xml(document.get_cached_xml(lang)).decode('utf8')
        # Check if a document has changed after normalizing XML and removing all whitespace.
        # This does risk missing changes to e.g. typos caused by missing whitespace,
        # but it avoids flagging many irrelevant whitespace changes.
        changed = _remove_whitespace(new_xml) != _remove_whitespace(old_xml)
        result[lang] = changed
        if changed and print_diff:
            print(document)
            diff = difflib.unified_diff(
                [l.strip() for l in old_xml.splitlines()], 
                [l.strip() for l in new_xml.splitlines()], n=0, lineterm='')
            print("\n".join(diff))

    if reimport and document.skip_redownload:
        print("Document is marked to skip redownload, skipping reimport")
        return result

    if prompt_to_import and True in result.values():
        print("Import this document? (y/n)")
        if input().strip() != 'y':
            return result
        reimport = True

    if reimport and True in result.values():
        import_document(document, allow_reimport=True, prompt_on_slug_change=prompt_on_slug_change,
                        xml_en=xml_bytes['en'], xml_fr=xml_bytes['fr'])
        document.save_xml(xml_urls['en'], xml_bytes['en'], xml_bytes['fr'], overwrite=True)
        print("Reimported %r" % document)
    return result

def force_redownload(document: Document):
    def _get(lang):
        resp = requests.get(document.get_xml_url(lang))
        resp.raise_for_status()
        return resp.content.replace(b'\r\n', b'\n')
    xml_en, xml_fr = _get('en'), _get('fr')
    document.save_xml(document.get_xml_url('en'), xml_en, xml_fr, overwrite=True)
    return document.get_xml_path('en')

def reimport_documents(documents: Iterable[Document], reimport=True, prompt_on_slug_change=False,
                       prompt_to_import=False, print_diff=False) -> list[Document]:
    failures = []
    for doc in documents:
        if doc.skip_redownload:
            continue
        try:
            check_for_xml_updates(doc, reimport=reimport, print_diff=print_diff,
                                  prompt_on_slug_change=prompt_on_slug_change, prompt_to_import=prompt_to_import)
        except Exception as e:
            logger.error("Error reimporting %r: %r", doc, e)
            failures.append(doc)
    return failures

INTERVALS = [1,2,3,7,14,21,30,50,100,150,200,300,400,550,700,1000]
def reimport_recent_documents(intervals=INTERVALS):
    today = datetime.date.today()
    target_dates = [today - datetime.timedelta(days=i) for i in intervals]
    docs = Document.objects.filter(downloaded=True, skip_redownload=False).filter(
        models.Q(first_imported__date__in=target_dates) |
        models.Q(first_imported__isnull=True, date__in=target_dates))
    failures = reimport_documents(docs)
    if failures:
        print("\n\nFailures:")
        for f in failures:
            print(f)
