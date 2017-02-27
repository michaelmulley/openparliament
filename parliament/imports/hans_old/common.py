# coding: utf-8
"""This module parses the Hansards of the House from HTML

There are two parsers, for two different HTML formats (1994-2006, 2006-).

However, XML is now available for the 2006-present documents, and
the (better) parser for that is in parl_document.py and the
alpheus module.

In other words, this module is historical and unmaintained. Interfaces
with the outside world are probably broken.

This module is organized like so:
__init__.py - utility functions, simple parse interface
common.py - infrastructure used in the parsers, i.e. regexes
current.py - parser for the Hansard format used from 2006 to the present
old.py - (fairly crufty) parser for the format used from 1994 to 2006

"""
import re, urllib, urllib2, datetime, sys, codecs

from BeautifulSoup import BeautifulSoup, Comment, NavigableString
from django.db.models import Q
from django.db import transaction
from django.utils.html import escape
from django.conf import settings

from parliament.core.models import *
from parliament.hansards.models import Statement
from parliament.hansards.models import Document as Hansard
from parliament.bills.models import Bill
from parliament.core import parsetools
from parliament.core.parsetools import r_politicalpost, r_honorific, r_notamember

ENABLE_READLINE = False
ENABLE_PRINT = False
GET_PARLID_ONLINE = True
VERBOSE = False
SAVE_GENDER = True

## REGEXES
r_time_paren = re.compile(r'^\s*D?\s*\(\s*(\d\d)(\d\d)\s*\)\s*$', re.UNICODE)
r_time_noparen = re.compile(r'^\s*(\d\d)(\d\d)\s*$', re.UNICODE)
r_time_optionalparen = re.compile(r'\s*\(?\s*(\d\d)(\d\d)\s*\)?\s*$', re.UNICODE)
r_time_glyph = re.compile(r'arobas\.gif')
r_arrow_img = re.compile(r'arrow\d+\.gif')
r_housemet = re.compile(r'The\s+House\s+met\s+at\s+(\d[\d:\.]*)\s+([ap]\.m\.)', re.I | re.UNICODE)
r_proceedings = re.compile(r'^\s*The\s+House\s+(resumed|proceeded)', re.UNICODE)

r_letter = re.compile(r'\w')
r_notspace = re.compile(r'\S', re.UNICODE)
r_timeanchor = re.compile(r'^T\d\d\d\d$')
r_division = re.compile(r'^\s*\(?\s*Division\s+No\.\s+\d+\s*\)\s*$', re.I | re.UNICODE)
r_letterbutnotD = re.compile(r'[a-zA-CE-S]')

STARTUP_RE = (
    (re.compile(r'Peri</b>\s*G\s*<b>', re.I), 'Peric '),  # hardcoded just for you, Janko. mwah.
    (re.compile(r'<b>—</b>', re.I), '—'),
)
STARTUP_RE_1994 = (
    # Deal with self-closing <a name> tags
    (re.compile(r'<a name="[^"]+" />'), ''),# we're just getting rid of them, since we don't care about them
    # And empty bold tags
    (re.compile(r'</?b>(\s*)</?b>', re.I | re.UNICODE), r'\1'), 
    # Another RE for empty bolds
    (re.compile(r'<b>[^\w\d<]+</b>', re.I | re.UNICODE), ' '),
    # And line breaks or <hr>
    (re.compile(r'</?[bh]r[^>]*>', re.I), ''),
    # And [<i>text</i>]
    (re.compile(r'\[<i>[^<>]+</i>\]', re.I), ''),
    (re.compile(r'Canadian Alliance, PC/DR'), 'Canadian Alliance / PC/DR'),
    (re.compile(r'Mr\. Antoine Dubé Lévis'), 'Mr. Antoine Dubé (Lévis'), # antoine comes up often
    (re.compile(r'Hon\. David Anderson:'), 'Hon. David Anderson (Victoria):'),
    (re.compile(r'<b>>', re.I), '<b>'),
    (re.compile(r'<>'), ''),
)
STARTUP_RE_2009 = (
    (re.compile(r'<b>\s*<A class="WebOption" onclick="GetWebOptions\(\'PRISM\',\'Affiliation\'[^>]+></a>\s*</b>', re.I | re.UNICODE), '<b><a class="deleteMe"></a></b>'), # empty speaker links -- will be further dealt with once we have a parse tree
    (re.compile(r'&nbsp;'), ' '),
    (re.compile(r'<div>\s*<b>\s*</b>\s*</div>', re.I | re.UNICODE), ' '), # <div><b></b></div>
    # Another RE for empty bolds
    (re.compile(r'<b>[^\w\d<]*</b>', re.I | re.UNICODE), ''),    
)




class ParseTracker(object):
    def __init__(self):
        self._current = dict()
        self._next = dict()
        self._textbuffer = []
        self._ignoretext = False
        
    def __setitem__(self, key, val):
        self._current[key] = val
    
    def setNext(self, key, val):
        self._next[key] = val
        
    def __getitem__(self, key):
        try:
            return self._current[key]
        except KeyError:
            return None
    
    def hasText(self):
        return len(self._textbuffer) >= 1
        
    def ignoreText(self, ignore=True):
        self._ignoretext = ignore
        
    def ignoringText(self):
        return self._ignoretext
         
    def addText(self, text, blockquote=False):
        if not self._ignoretext:
            t = parsetools.tameWhitespace(text.strip())
            t = parsetools.sane_quotes(t)
            if t.startswith(':'):
                # Strip initial colon
                t = t[1:].strip()
            if t.startswith('He said: '):
                t = t[8:].strip()
            if t.startswith('She said: '):
                t = t[9:].strip()
            if len(t) > 0 and not t.isspace():
                #if t[0].islower() and not t.startswith('moved'):
                #    print "WARNING: Block of text begins with lowercase letter: %s" % t
                if blockquote or (t.startswith('moved ') and not self.hasText()):
                    self._textbuffer.append(u'> ' + t)
                else:
                    self._textbuffer.append(t)
                    
    def appendToText(self, text, italic=False):
        if self.hasText() and not self._ignoretext:
            t = parsetools.tameWhitespace(text.strip())
            if len(t) > 0 and not t.isspace():
                if italic: t = u' <em>' + t + u'</em> '
                self._textbuffer[-1] += t
        
    def getText(self):
        return u"\n\n".join(self._textbuffer)
        
    def onward(self):
        self._textbuffer = []
        self._current = self._next.copy()
        self._ignoretext = False
        
class ParseException(Exception):
    pass

class HansardParser(object):
    """Base class for Hansard parsers"""
    def __init__(self, hansard, html):
        super(HansardParser, self).__init__()
        self.hansard = hansard
        for regex in STARTUP_RE:
            html = re.sub(regex[0], regex[1], html)

        self.soup = BeautifulSoup(html, convertEntities='html')
        
        # remove comments
        for t in self.soup.findAll(text=lambda x: isinstance(x, Comment)):
            t.extract()
        
    def parse(self):
        self.statements = []
        self.statement_index = 0
        
    def houseTime(self, number, ampm):
        ampm = ampm.replace('.', '')
        number = number.replace('.', ':')
        match = re.search(r'(\d+):(\d+)', number)
        if match:
            # "2:30 p.m."
            return datetime.datetime.strptime("%s:%s %s" % (match.group(1), match.group(2), ampm), "%I:%M %p").time()
        else:
            # "2 p.m."
            return datetime.datetime.strptime("%s %s" % (number, ampm), "%I %p").time()
            
    def saveProceedingsStatement(self, text, t):
        text = parsetools.sane_quotes(parsetools.tameWhitespace(text.strip()))
        if len(text):
            timestamp = t['timestamp']
            if not isinstance(timestamp, datetime.datetime):
                # The older parser provides only datetime.time objects
                timestamp = datetime.datetime.combine(self.date, timestamp)
            statement = Statement(hansard=self.hansard,
                time=timestamp,
                text=text, sequence=self.statement_index,
                who='Proceedings')
            self.statement_index += 1
            self.statements.append(statement)
        
    def saveStatement(self, t):
        def mcUp(match):
            return 'Mc' + match.group(1).upper()
        if t['topic']:
            # Question No. 139-- -> Question No. 139
            t['topic'] = re.sub(r'\-+$', '', t['topic'])
            t['topic'] = re.sub(r"'S", "'s", t['topic'])
            t['topic'] = re.sub(r'Mc([a-z])', mcUp, t['topic'])
        if t.hasText():
            if not t['member_title']:
                t['member_title'] = 'Proceedings'
                print "WARNING: No title for %s" % t.getText().encode('ascii', 'replace')
            timestamp = t['timestamp']
            if not isinstance(timestamp, datetime.datetime):
                # The older parser provides only datetime.time objects
                timestamp = datetime.datetime.combine(self.date, timestamp)
            statement = Statement(hansard=self.hansard, heading=t['heading'], topic=t['topic'],
             time=timestamp, member=t['member'],
             politician=t['politician'], who=t['member_title'],
             text=t.getText(), sequence=self.statement_index, written_question=bool(t['written_question']))
            if r_notamember.search(t['member_title'])\
              and ('Speaker' in t['member_title'] or 'The Chair' in t['member_title']):
                statement.speaker = True
            self.statement_index += 1
            self.statements.append(statement)
            
            if ENABLE_PRINT:
                print u"HEADING: %s" % t['heading']
                print u"TOPIC: %s" % t['topic']
                print u"MEMBER TITLE: %s" % t['member_title']
                print u"MEMBER: %s" % t['member']
                print u"TIME: %s" % t['timestamp']
                print u"TEXT: %s" % t.getText()
            if ENABLE_READLINE:
                sys.stdin.readline()
        t.onward()