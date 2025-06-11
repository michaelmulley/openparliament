# Parses XML transcript, of Hansards and committee evidence,
# from ourcommons.ca. Produces either an HTML file or a bunch of objects,
# containing mostly HTML, used by parl_document.py.

from html import escape as stdlib_escape
import datetime
from functools import wraps
import re
from xml.sax.saxutils import quoteattr

from lxml import etree

import logging
logger = logging.getLogger(__name__)

__all__ = ['parse_bytes']

def _n2s(o):
    return o if o is not None else ''
        
def _build_tag(name, attrs):
    return '<%s%s>' % (
        name,
        ''.join((
            " %s=%s" % (k, quoteattr(str(v)))
            for k,v in sorted(attrs.items())
        ))
    )

_r_whitespace = re.compile(r'\s+', re.UNICODE)
def _tame_whitespace(s):
    return _r_whitespace.sub(' ', _n2s(s)).strip()
    
def _text_content(el, tail=False):
    return _tame_whitespace(
        _n2s(el.text) + 
        ''.join([_text_content(subel, True) for subel in el]) + 
        (_n2s(el.tail) if tail else ''))
        
def _letters_only(s):
    return re.sub('[^a-zA-Z]', '', _n2s(s).lower())
        
def _smart_title(s):
    if s.isupper() or s.islower():
        return s.title()
    return s
    
def _following_char(el):
    """Returns the next non-whitespace character after this element,
    without moving up the tree."""
    tail = _n2s(el.tail).strip()
    if tail:
        return tail[0]
    nxt = el.getnext()
    if nxt is not None:
        txt = _n2s(nxt.text).strip()
        if txt:
            return txt[0]
    return ''
    
def _only_open(target):
    """Only execute the function if argument openclose == TAG_OPEN"""
    @wraps(target)
    def inner(self, el, openclose, *args, **kwargs):
        if openclose == TAG_OPEN:
            return target(self, el, openclose, *args, **kwargs)
    return inner

def escape(s):
    """Escape HTML entities in a string. A wrapper around the Python function, since we don't want
    to escape quotation marks."""
    return stdlib_escape(s, quote=False)

_r_housemet = re.compile(r'^\s*(?P<text>The\s+House\s+met\s+at|La\s+séance\s+est\s+ouverte\s+à)\s+(?P<number>\d[\d:\.]*)\s*(?P<ampm>[ap]\.m\.|)', re.I | re.UNICODE)
_r_person_label = re.compile(r'^(Mr\.?\s|Mrs\.?\s|Ms\.?\s|Miss\.?s\|Hon\.?\s|Right\sHon\.\s|The\sSpeaker|Le\sprésident|The\sChair|The\sDeputy|The\sActing|An\s[hH]on\.?\s|Une\svoix|Des\svoix|Some\s[hH]on\.\s|M\.\s|Acting\s|L.hon\.?\s|Le\strès\s|Assistant\s|Mme\.?\s|Mlle\.?\s|Dr\.?\s)', re.UNICODE)
_r_honorific = re.compile(r'^(Mr\.?\s|Mrs\.?\s|Ms\.?\s|Miss\.?\s|Hon\.?\s|Right\sHon\.\s|M\.\s|L.hon\.?\s|Mme\.?\s|Mlle\.?\s|Dr\.?\s)', re.UNICODE)
_r_parens = re.compile(r'\s*\(.+\)\s*')
_r_indeterminate = re.compile(r'^(An?|Une)\s')
_r_bill_stage = re.compile(r'\s*(?:Projet de loi|Bill)\s+(?P<cs>[CS]).(?P<number_only>\d+)[,:\-\.\s]+(?P<stage>.+)', re.I)
BILL_STAGES = [
    ('first reading', '1'),
    ('première lecture', '1'),
    ('senate', 'senate'),
    ('du sénat', 'senate'),
    ('second reading', '2'),
    ('deuxième lecture', '2'),
    ('third reading', '3'),
    ('troisième lecture', '3'),
    ('report stage', 'report'),
    ('étape du rapport', 'report'),
]

def _get_housemet_time(number, ampm):
    ampm = _n2s(ampm).replace('.', '')
    number = number.replace('.', ':')
    match = re.search(r'(\d+):(\d+)', number)
    if match:
        hour = match.group(1)
        minute = match.group(2)
    else:
        hour = number
        minute = '00'
    if ampm:
        return datetime.datetime.strptime("%s:%s %s" % (hour, minute, ampm), "%I:%M %p").time()
    else:
        return datetime.time(hour=int(hour), minute=int(minute))
        
def _time_to_datetime(hour, minute, date):
    """Given hour, minute, and a datetime.date, returns a datetime.datetime.

    Necessary to deal with the occasional wacky 25 o'clock timestamps in Hansard.
    """
    if hour < 24:
        return datetime.datetime.combine(date, datetime.time(hour=hour, minute=minute))
    else:
        return datetime.datetime.combine(
            date + datetime.timedelta(days=hour//24),
            datetime.time(hour=hour % 24, minute=minute)
        )
        
def _strip_person_name(n):
    return _r_honorific.sub('', _r_parens.sub('', _tame_whitespace(n))).strip()
        
class AlpheusError(Exception):
    pass
        
class AlpheusDocument(object):
    
    BASE_HTML = """<!DOCTYPE html>
    <html lang="%(lang)s"><head>
    <meta charset="utf-8">
    <title>%(title)s</title>
    <link rel="stylesheet" type="text/css" href="https://michaelmulley.github.io/alpheus/alpheus.css">
    </head>
    <body><h1>%(title)s</h1>
    <table>%(metadata_rows)s</table>
    %(statements)s
    </body></html>
    """
    
    def as_html(self) -> str:
        if self.meta['document_type'].lower() == 'committee':
            if self.meta['language'].lower() == 'en':
                title = self.meta['committee_name_en']
            else:
                title = self.meta['committee_name_fr']
        elif self.meta['document_type'].lower() == 'debates':
            if self.meta['language'].lower() == 'en':
                title = 'House Debates'
            else:
                title = 'Débats du Chambre'
        title += ', ' + str(self.meta['date'])
        
        metadata_rows = []
        for k, v in sorted(self.meta.items()):
            metadata_rows.append("%s<th>%s</th><td>%s</td></tr>" % (
                _build_tag('tr', {'class': 'metadata', 'data-name': k, 'data-value': v}),
                escape(k), escape(str(v))))
        
        html = self.BASE_HTML % {
            'title': title,
            'lang': self.meta['language'],
            'metadata_rows': '\n'.join(metadata_rows),
            'statements': '\n'.join((s.as_html().replace('</p>', '</p>\n\t') for s in self.statements))
        }
        return html
        
    def __init__(self):
        self.meta = {}
        
    
class Statement(object):
    
    def __init__(self, attributes, more_attributes):
        self.meta = dict(attributes)
        self.meta.update(more_attributes)
        self.content = ''
        
    def clean_up_content(self):
        self.content = _tame_whitespace(self.content)
        self.content = self.content.replace('</blockquote><blockquote>', '')
        if 'id' not in self.meta:
            self.meta['id'] = 'p' + re.search(r'data-HoCid="(\d+)"', self.content).group(1)
        
    def as_html(self):
        def setval(in_key, out_key):
            if self.meta.get(in_key):
                attrs[out_key] = str(self.meta[in_key])
                
        attrs = {
            'class': 'statement',
            'data-timestamp': str(self.meta['timestamp']), #.strftime("%H:%M"),
        }
        setval('id', 'id')
        setval('person_attribution', 'data-person-speaking-attribution')
        setval('person_id', 'data-person-speaking-HoCid')
        setval('person_type', 'data-person-speaking-type')
        setval('h1', 'data-h1')
        setval('h2', 'data-h2')
        setval('h3', 'data-h3')
        setval('intervention_type', 'data-intervention-type')
        setval('written_question', 'data-written-question')
        setval('bill_stage', 'data-bill-stage')
        return _build_tag('div', attrs) + self.content + '</div>'

class ParseHandler(object):
    """This class contains the bulk of the parsing logic.
    
    The parse tree is iterated through in document order. Every time we come
    across a tag (opening or closing) we call the handle_TagName method on
    a ParseHandler instance. That method is passed the Element object, and
    either TAG_OPEN or TAG_CLOSE."""
    
    # Their contents will be discarded
    EXCLUDE_TAGS = [
        'CatchLine', # I don't really know what this tag means. It generally repeats a heading provided elsewhere
        'Prayer',
        'QuestionID', # This is actually processed in handle_WrittenQuestionResponse
        'Appendix', # Too much of a catch-all category to process properly
    ]
    
    # We include these tags, though we discard attributes and may change the name
    PASSTHROUGH_TAGS = {
        'I': 'em',
        'Sup': 'sup',
        'Sub': 'sub',
        'table': 'table',
        'row': 'tr',
        'entry': 'td',
    }
    
    # We include the text contents of the tag. Tags in this list won't generate
    # "unknown tag" errors
    IGNORE_TAGS = ['Quote', 'QuotePara', 'ForceColumnBreak',
                    'SubjectOfBusinessContent', 'Content', 'HansardBody',
                    'Intro', 'Poetry', 'Query', 'Motion',
                    'MotionBody', 'CommitteeQuote', 'LegislationQuote',
                    'Pause', 'StartPause', 'EndPause', 'Date', 'Insertion',
                    'colspec', 'tgroup', 'tbody', 'thead', 'title',
                    'EditorsNotes',
                    etree.ProcessingInstruction] + list(PASSTHROUGH_TAGS.keys())

        
    def __init__(self, document):
        self.statements = []
        self.current_statement = None
        self.document_language = document.meta['language'].lower()
        self.current_attributes = {
            'language': self.document_language
        }
        self.one_time_attributes = {}
        self.in_para = False
        self.one_liner = None
        self.people_seen = {}
        self.people_types_seen = {}
        self.people_contexts = {}
        self.date = document.meta['date']
        self.main_statement_speaker = ['', '']
        (self.parliament, self.session) = (document.meta['parliament'], document.meta['session'])
        
    def _initialize_statement(self):
        assert not self.current_statement
        self.current_statement = Statement(self.current_attributes, self.one_time_attributes)
        self.one_time_attributes = {}
    
    def _add_code(self, s):
        """Add an unescaped value, i.e. HTML, to the current statement."""
        if not s:
            return
        if not self.current_statement:
            self._initialize_statement()
        self.current_statement.content += s
        
    def _add_text(self, s):
        """Add text (that will be escaped) to the current statement."""
        if s:
            self._add_code(escape(s))
        
    def _add_tag_text(self, el, openclose):
        """Add the text in this tag's text/tail, as appropriate, to the current statement."""
        if openclose == TAG_OPEN:
            if not el.get('alpheus_skip_text'):
                self._add_text(el.text)
        else:
            self._add_text(el.tail)
            
    def close_statement(self):
        """Whoever's currently speaking has stopped: finalize this Statement object."""
        if self.current_statement:
            #if not self.current_statement.meta.get('has_non_procedural'):
            #    for key in ('person_attribution', 'person_id', 'person_type'):
            #        self.current_statement.meta.pop(key, None)
            self.current_statement.clean_up_content()
            if not self.current_statement.content.strip():
                raise AlpheusError("Trying to save a statement without content")
            self.statements.append(self.current_statement)
            self.current_statement = None
            
    def get_final_statements(self):
        if self.current_statement and self.current_statement.content.strip():
            self.close_statement()
        return self.statements
        
    def _new_person(self, hoc_id, description, affil_type=None):
        """Someone new has started speaking; save their information."""
        description = _tame_whitespace(description)
        stripped_description = _strip_person_name(description)
        if self.current_statement:
            # If this "new person" is the same as the last person,
            # don't start a new statement
            if ((hoc_id and hoc_id == self.current_statement.meta.get('person_id'))
              or ((not hoc_id) and 
              _letters_only(stripped_description) == _letters_only(_strip_person_name(self.current_statement.meta.get('person_attribution'))))):
                if not _r_indeterminate.search(description):
                    # (Though if it's "An hon. member", two in a row *can* be different people.)
                    return False
            self.close_statement()
        self.one_time_attributes['person_attribution'] = description
        if hoc_id:
            self.one_time_attributes['person_id'] = hoc_id
        else:
            # If we don't have an ID, see if we previously got one for this person
            if stripped_description in self.people_seen:
                self.one_time_attributes['person_id'] = self.people_seen[stripped_description]
        
        # The "Affiliation Type" field is so far mysterious -- it has scores of
        # different values in use -- but I've made guesses at a few values
        if affil_type == '28':
            self.one_time_attributes['person_type'] = 'witness'
        elif affil_type == '27':
            self.one_time_attributes['person_type'] = 'clerk'
        elif affil_type == '26':
            self.one_time_attributes['person_type'] = 'analyst'
        elif not affil_type and stripped_description in self.people_types_seen:
            self.one_time_attributes['person_type'] = self.people_types_seen[stripped_description]
            
        context_match = re.search(r'\s?\((.+)\)\s*$', description)
        if context_match:
            self.one_time_attributes['person_context'] = context_match.group(1)
        elif stripped_description in self.people_contexts:
            self.one_time_attributes['person_context'] = self.people_contexts[stripped_description]
            
        for key in (description, stripped_description):
            # Save backreferences in case we later lack extra data
            if hoc_id:
                self.people_seen[key] = hoc_id
            if self.one_time_attributes.get('person_type'):
                self.people_types_seen[key] = self.one_time_attributes['person_type']
            if self.one_time_attributes.get('person_context'):
                self.people_contexts[key] = self.one_time_attributes['person_context']
                
    def _is_person(self):
        """Do we know who's speaking the current text?"""
        attributes = self.current_statement.meta if self.current_statement else self.one_time_attributes
        return bool(attributes.get('person_attribution') or attributes.get('person_id'))
    
    def handle_ParaText(self, el, openclose, procedural=None):
        if openclose == TAG_OPEN:
            
            mytext = _n2s(el.text).strip()
            if not mytext and not _text_content(el):
                # Ignore empty paragraphs
                return NO_DESCEND
            # ParaText has a bunch of special cases
            if _r_housemet.search(mytext) and el.getparent().tag == 'Intro':
                # "The House met at 10 a.m."
                match = _r_housemet.search(el.text)
                self.current_attributes['timestamp'] = datetime.datetime.combine(
                    self.date, _get_housemet_time(match.group('number'), match.group('ampm')))
                return NO_DESCEND
            
            sub = list(el)

            # If the paragraph is immediately followed by a B or Affiliation tag,
            # that usually means it's actually something being said by someone else    
            if (
                    (not mytext)
                    and sub and sub[0].tag in ('B', 'Affiliation') and sub[0].text and sub[0].text.strip()
                    and sub[0].text.strip()[0].isupper()
                    and _following_char(sub[0])
                    # it's a B or Affiliation tag, which has stuff both within it and directly after
                    and (
                        # there's a colon
                        sub[0].text.strip().endswith(':') 
                        or _following_char(sub[0]) == ':'
                        # or the paragraph is tagged as an interjection
                        or el.get('Interjection')
                        # or it looks like it starts with a title
                        or (_r_person_label.search(sub[0].text.strip()) and _following_char(sub[0]).isupper())
                    )):
                # MONSTER IF COMPLETE. It looks like a new speaker.
                if sub[0].tag == 'Affiliation':
                    hoc_id = sub[0].get('DbId')
                else:
                    hoc_id = None
                person_attribution = _tame_whitespace(sub[0].text.replace(':', ''))
                if (hoc_id != self.main_statement_speaker[0]
                  and (not _letters_only(self.main_statement_speaker[1]).startswith(
                  _letters_only(person_attribution)))
                  and not _r_honorific.search(person_attribution)):
                  # If we're not switching back to the main speaker,
                  # and this is an interjection from a generic role -- e.g. Des voix --
                  # save a flag to switch back on the next line.
                    self.one_liner = (True, el.getparent())
                else:
                    self.one_liner = None
                self._new_person(hoc_id, sub[0].text.replace(':', '').strip())
                if not sub[0].text.endswith(':') and (sub[0].tail and sub[0].tail[0] == ':'):
                    # If the colon is on the wrong side of the B, stop it from
                    # showing up in the paragraph text
                    sub[0].tail = sub[0].tail[1:]
                sub[0].set('alpheus_skip_text', 'true')
            elif self.one_liner:
                # The last paragraph was a quick interjection -- switch back
                # to the previous speaker if one wasn't labelled
                if self.one_liner[1] == el.getparent():
                    self._new_person(self.main_statement_speaker[0], self.main_statement_speaker[1])
                self.one_liner = None
                
            self.in_para = True
            
            if not self._is_person():
                if self.current_attributes.get('h2', '').lower() in ('speech from the throne', 'le discours du trône') \
                        and not self.current_attributes.get('h3'):
                    self.handle_ThroneSpeech(el, TAG_OPEN)
                else:
                    procedural = True
                
            if mytext.startswith('moved') or mytext.startswith('demande'):
                procedural = True
                nxt = el.getnext()
                while nxt is not None and (nxt.tag != 'ParaText' or nxt.xpath('.//QuotePara')):
                    # Find the next paragraph after the motion
                    nxt = nxt.getnext()
                if nxt is not None and nxt.text:
                    # After a motion, there's an unnecessary "He said:" on the next phrase
                    nxt.text = re.sub(r'^\s*([S]?[hH]e said:|--)\s*', '', nxt.text)
                    
            if mytext and mytext[0] in ('(', '['):
                procedural = True
                      
            p_attrs = {
                'data-HoCid': el.get('id', '0')
            }

            if procedural:
                p_attrs['class'] = 'procedural'
            else:
                if self.current_statement:
                    self.current_statement.meta['has_non_procedural'] = True
                else:
                    self.one_time_attributes['has_non_procedural'] = True
                if self.current_attributes.get('language'):
                    p_attrs['data-originallang'] = self.current_attributes['language']
            
            if el.xpath('.//QuotePara'):
                self._add_code('<blockquote>')
            self._add_code(_build_tag('p', p_attrs)) 
            self._add_tag_text(el, openclose)
        else:
            assert self.in_para
            self.in_para = False
            self._add_code('</p>')
            if el.xpath('.//QuotePara'):
                self._add_code('</blockquote>')
            assert not _n2s(el.tail).strip()
                        
    def handle_ProceduralText(self, el, openclose):
        assert not _n2s(el.tail).strip()
        if el.get('TocType') == 'TPC':
            if openclose == TAG_OPEN:
                stage_match = _r_bill_stage.match(_text_content(el))
                if stage_match or self.current_attributes.get('bill_stage'):
                    if stage_match:
                        bill_number = stage_match.group('cs') + '-' + stage_match.group('number_only')
                        raw_stage_name = stage_match.group('stage')
                    else:
                        bill_number = self.current_attributes['bill_stage'].split(',')[0]
                        raw_stage_name = el.text
                    stage_code = f'other[{raw_stage_name}]'
                    raw_stage_name = raw_stage_name.lower()
                    for stage, code in BILL_STAGES:
                        if stage in raw_stage_name:
                            stage_code = code
                            break
                    if stage_match or not stage_code.startswith('other'):
                        # In the case where the text didn't include the bill number (not stage_match),
                        # we only want to update to a recognized bill stage like a reading;
                        # otherwise there's a bunch of stuff like "Amendment negatived" which is not
                        # in fact a bill stage
                        self.current_attributes['bill_stage'] = f"{bill_number},{stage_code}"
                        if self.current_statement:
                            self.current_statement.meta['bill_stage'] = self.current_attributes['bill_stage']
                return NO_DESCEND
                #self._add_code('<!-- ProceduralText ')
                #self._add_tag_text(el, openclose)
                #self._add_code(' -->')
        else:
            return self.handle_ParaText(el, openclose, procedural=True)
            
    handle_ThroneSpeechPara = handle_ParaText
    
    @_only_open
    def handle_ThroneSpeech(self, el, openclose):
        throne = ("The Governor General", "Le gouverneur général")
        if int(self.parliament) == 45 and int(self.session) == 1:
            throne = ("King Charles III", "Le roi Charles III")
        self._new_person(None, 
            throne[0] if self.document_language[0] == 'e' else throne[1])

    def handle_B(self, el, openclose):
        # Fallout from new-speaker special case in ParaText
        if el.text == ':':
            el.set('alpheus_skip_text', 'true')
        if not el.get('alpheus_skip_text'):
            self._add_code('<%sstrong>' % ('/' if openclose == TAG_CLOSE else ''))
        self._add_tag_text(el, openclose)
            
    def handle_Verse(self, el, openclose):
        if openclose == TAG_OPEN:
            self._add_code('<span class="verse">')
        else:
            self._add_code('</span>')
        self._add_tag_text(el, openclose)
            
    def handle_Line(self, el, openclose):
        # Appears within <Poetry> and <Verse> tags
        if openclose == TAG_CLOSE:
            self._add_code('<br>')
        self._add_tag_text(el, openclose)
    
    @_only_open
    def handle_PersonSpeaking(self, el, openclose):
        try:
            affil = el.xpath('Affiliation')[0]
        except IndexError:
            logger.warning("No affiliation in PersonSpeaking: %s" % etree.tostring(el))
            return NO_DESCEND
        if not affil.text:
            logger.warning("Empty affiliation: %s" % etree.tostring(el))
            return NO_DESCEND
        self._new_person(affil.get('DbId'), affil.text, affil.get('Type'))
        self.main_statement_speaker = (affil.get('DbId'), affil.text, affil.get('Type'))
        if affil.tail and affil.tail.replace(':', '').strip():
            content = affil.tail.replace(':', '').strip()
            if not content.startswith('('):
                # logger.warning("Looks like there's content in PersonSpeaking: %s" % content)
                self._add_text(content)
        return NO_DESCEND
        
    handle_Questioner = handle_PersonSpeaking
    handle_Responder = handle_PersonSpeaking
        
    def handle_Intervention(self, el, openclose):
        if openclose == TAG_OPEN:
            self.one_time_attributes['intervention_type'] = el.get('Type')
            self.one_time_attributes['id'] = el.get('id')
        else:
            self.close_statement()
    
    @_only_open
    def handle_FloorLanguage(self, el, openclose):
        lang = el.get('language', '').lower()
        if lang in ('en', 'fr'):
            self.current_attributes['language'] = lang
        else:
            self.current_attributes['language'] = None
        return NO_DESCEND
    
    @_only_open
    def handle_Timestamp(self, el, openclose):
        if el.get('Hr'):
            self.current_attributes['timestamp'] = _time_to_datetime(
                hour=int(el.get('Hr').replace(' ', '')), minute=int(el.get('Mn', 0)), date=self.date)
            if self.current_statement and not self.current_statement.meta.get('has_non_procedural'):
                # If there's only been procedural text so far, make this timestamp apply to the current
                # statement
                self.current_statement.meta['timestamp'] = self.current_attributes['timestamp']
        return NO_DESCEND
        
    def handle_SubjectOfBusinessQualifier(self, el, openclose):
        self.current_attributes['h3'] = _text_content(el)
        return NO_DESCEND
        
    def handle_SubjectOfBusinessTitle(self, el, openclose):
        self.current_attributes['h2'] = _text_content(el)
        if 'bill_stage' in self.current_attributes:
            del self.current_attributes['bill_stage']
        return NO_DESCEND
        
    def handle_SubjectOfBusiness(self, el, openclose):
        if openclose == TAG_CLOSE:
            if 'h3' in self.current_attributes:
                del self.current_attributes['h3']
            
    def handle_OrderOfBusiness(self, el, openclose):
        if openclose == TAG_CLOSE:
            if 'h1' in self.current_attributes:
                del self.current_attributes['h1']
            if 'h2' in self.current_attributes:
                del self.current_attributes['h2']
            if 'bill_stage' in self.current_attributes:
                del self.current_attributes['bill_stage']                
        
    def handle_OrderOfBusinessTitle(self, el, openclose):
        self.current_attributes['h1'] = _smart_title(_text_content(el))
        return NO_DESCEND
        
    def handle_WrittenQuestionResponse(self, el, openclose):
        if openclose == TAG_OPEN:
            if el.xpath('QuestionID'):
                qid = el.xpath('QuestionID')[0]
                self.current_attributes['h3'] = \
                    _text_content(qid).replace('--', '').strip()
        else:
            if self.current_attributes.get('h3', '').lower().startswith('question'):
                del self.current_attributes['h3']
    
    def handle_QuestionContent(self, el, openclose):
        if openclose == TAG_OPEN:
            self.one_time_attributes['written_question'] = 'question'
        else:
            self.close_statement()
    
    def handle_ResponseContent(self, el, openclose):
        if openclose == TAG_OPEN:
            self.one_time_attributes['written_question'] = 'response'
        else:
            self.close_statement()
        
    def handle_Affiliation(self, el, openclose):
        if (not el.get('alpheus_skip_text')) and el.get('DbId'):
            if openclose == TAG_OPEN:
                attrs = {
                    'href': 'http://www.parl.gc.ca/MembersOfParliament/ProfileMP.aspx?Key=%s&Language=%s' % (
                        el.get('DbId'), self.document_language[0].upper()),
                    'data-HoCid': el.get('DbId'),
                    'class': 'related_link politician'
                }
                self._add_code(_build_tag('a', attrs))
            else:
                self._add_code('</a>')
        self._add_tag_text(el, openclose)
            
    def handle_Document(self, el, openclose):
        if el.get('DbId'):
            if openclose == TAG_OPEN:
                attrs = {
                    'href': 'http://www.parl.gc.ca/LegisInfo/BillDetails.aspx?&Mode=1&billId=%s&Language=%s' % (
                        el.get('DbId'), self.document_language[0].upper()),
                    'data-HoCid': el.get('DbId'),
                    'class': 'related_link legislation'
                }
                self._add_code(_build_tag('a', attrs))
            else:
                self._add_code('</a>')
        self._add_tag_text(el, openclose)
        
    def handle_Division(self, el, openclose):
        num = el.get('DivisionNumber')
        url = 'http://www.parl.gc.ca/HouseChamberBusiness/ChamberVoteDetail.aspx?Language=%s&Mode=1&Parl=%s&Ses=%s&Vote=%s' %(
            self.document_language[0].upper(), self.parliament, self.session, num)
        self._add_code('%s%sVote #%s</a></p>' % (
            _build_tag('p', {'class': 'division procedural'}),
            _build_tag('a', {'class': 'related_link vote', 'href': url, 
                    'data-number': num, 'data-HoCid': el.get('id')}),
            num))
        return NO_DESCEND
        
    def _default_handler(self, el, openclose):
        if el.tag in self.EXCLUDE_TAGS:
            return NO_DESCEND
        if el.tag in self.PASSTHROUGH_TAGS:
            self._add_code('<%s%s>' % (
                '/' if openclose == TAG_CLOSE else '',
                self.PASSTHROUGH_TAGS[el.tag]))
        if self.in_para:
            self._add_tag_text(el, openclose)
        if openclose == TAG_OPEN and el.tag not in self.IGNORE_TAGS:
            raise AlpheusError("I don't know how to handle tag %s" % el.tag)
        
    def __getattr__(self, name):
        # Route requests where we don't have a handler to the default
        if name.startswith('handle_'):
            return self._default_handler
        raise AttributeError("ParseHandler has no attribute %r" % name)        
    
NO_DESCEND = -1
TAG_OPEN = 1
TAG_CLOSE = 2
            
def parse_tree(tree):
    document = AlpheusDocument()
    
    # Start by getting metadata
    def _get_meta(key):
        return str(tree.xpath('//ExtractedItem[@Name="%s"]' % key)[0].text)
    document.meta['date'] = datetime.date(
        year=int(_get_meta('MetaDateNumYear')),
        month=int(_get_meta('MetaDateNumMonth')),
        day=int(_get_meta('MetaDateNumDay'))
    )
    document.meta['parliament'] = int(_get_meta('ParliamentNumber'))
    document.meta['session'] = int(_get_meta('SessionNumber'))
    
    hansard_tag = tree.xpath('/Hansard')[0]
    document.meta['language'] = hansard_tag.get('{http://www.w3.org/XML/1998/namespace}lang').lower()
    
    # The ID in the Hansard tag is *not* the same as the DocId in parl.gc.ca URLs
    # So to avoid confusion, we won't include it in the output
    #document.meta['id'] = hansard_tag.get('id')
    
    document.meta['document_type'] = _get_meta('MetaDocumentCategory')
    
    if document.meta['document_type'] == 'Committee':
        document.meta['committee_acronym'] = _get_meta('Acronyme')
        document.meta['committee_name_en'] = _get_meta('InstitutionDebateEn')
        document.meta['committee_name_fr'] = _get_meta('InstitutionDebateFr')
        #TODO: in camera
        
    document.meta['document_number'] = _get_meta('Number').split()[-1].lstrip('0')
    
    # Now we can move on to the content of the document
    handler = ParseHandler(document)
    
    def _explore_element(el):
        # Recursive depth-first search of the XML tree
        el_handler = getattr(handler, 'handle_' + str(el.tag))
        if el_handler(el, TAG_OPEN) != NO_DESCEND:
            for subelement in el:
                _explore_element(subelement)
            el_handler(el, TAG_CLOSE)
        
    _explore_element(tree.xpath('//HansardBody')[0])
    
    document.statements = handler.get_final_statements()
    return document
    
def parse_bytes(s: bytes) -> AlpheusDocument:
    s = s.replace(b'<B />', b'').replace(b'<ParaText />', b'') # Some empty tags can gum up the works
    s = s.replace(b'&ccedil;', b'&#231;').replace(b'&eacute;', b'&#233;') # Fix invalid entities
    return parse_tree(etree.fromstring(s))
