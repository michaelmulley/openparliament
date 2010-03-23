# coding: utf8
import re, urllib, urllib2, datetime, sys, codecs

from BeautifulSoup import BeautifulSoup, Comment, NavigableString
from django.db.models import Q

from parliament.core.models import *
from parliament.hansards.models import Hansard, Statement, HansardCache
from parliament.core import parsetools



# The publishing of the official publications of the House of Commons is governed by the law of parliamentary privilege, by which the House of Commons has the right to control the publication of its proceedings. It may be used without seeking the permission of the Speaker of the House of Commons provided that it is accurately reproduced and that it does not offend the dignity of the House of Commons or one of its Members. Reproduction of the material is permitted in whole or in part, and by any means. 
# http://www.parl.gc.ca/info/einfo_pubs.html

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
r_honorific = re.compile(r'^(Mr\.?|Mrs\.?|Ms\.?|Miss\.?|Hon\.?|Right Hon\.|The|A|An\.?|Some|M\.|One|Santa|Acting|L\'hon\.|Assistant|Mme)\s(.+)$', re.DOTALL | re.UNICODE)
r_notamember = re.compile(r'^(The|A|An|Some|Acting|Santa|One|Assistant|An\.)$')
r_politicalpost = re.compile(r'(Minister|Leader|Secretary|Solicitor|Attorney|Speaker|Deputy |Soliciter|Chair |Parliamentary|President |for )')
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
def qp(id):
    """Utility quick-parse function. Takes a Hansard ID"""
    return parseAndSave(Hansard.objects.get(pk=id))
    
def soup(id):
    cache = loadHansard(Hansard.objects.get(pk=id))
    parser = _getParser(cache.hansard, cache.getHTML())
    return parser.soup
    
def _getParser(hansard, html):
    if hansard.session.start.year < 2006:
        return HansardParser1994(hansard, html)
    else:
        return HansardParser2009(hansard, html)

def parseAndSave(arg):
    if isinstance(arg, Hansard):
        cache = loadHansard(arg)
    elif isinstance(arg, HansardCache):
        cache = arg
    else:
        raise Exception("Invalid argument to parseAndSave")
        
    if Statement.objects.filter(hansard=cache.hansard).count() > 0:
        print "There are already Statements for %s." % cache.hansard
        print "Delete them? (y/n) ",
        yn = sys.stdin.readline().strip()
        if yn == 'y':
            Statement.objects.filter(hansard=cache.hansard).delete()
        else:
            return False
    
    parser = _getParser(cache.hansard, cache.getHTML())
    
    statements = parser.parse()
    for statement in statements:
        try:
            statement.save()
        except Exception, e:
            print e
            raise Exception("Error %s saving statement: %s, %s" % (e, statement.who, statement.text))

def _getHansardNumber(page):
    title = re.search(r'<title>([^<]+)</title>', page).group(1)
    match = re.search(r'Number +(\d+\S*) ', parsetools.tameWhitespace(title)) # New format: Number 079
    if match:
        return re.sub('^0+', '', match.group(1))
    else:
        match = re.search(r'\((\d+\S*)\)', title) # Old format (079)
        if match:
            return re.sub('^0+', '', match.group(1))
        else:
            raise Exception("Couldn't parse number from Hansard title: %s" % title)
            
def loadHansard(hansard=None, url=None, session=None):
    if hansard:
        try:
            return HansardCache.objects.get(hansard=hansard)
        except HansardCache.DoesNotExist:
            if hansard.url:
                return loadHansard(url=hansard.url, session=hansard.session)
    elif url and session:
        normurl = parsetools.normalizeHansardURL(url)
        if normurl != url:
            print "WARNING: Normalized URL %s to %s" % (url, normurl)
        try:
            cached = HansardCache.objects.get(hansard__url=normurl)
            if cached.hansard.session != session:
                raise Exception("Found cached Hansard, but session doesn't match...")
            return cached
        except HansardCache.DoesNotExist:
            print "Downloading Hansard from %s" % normurl
            req = urllib2.Request(normurl)
            page = urllib2.urlopen(req).read()
            try:
                number = _getHansardNumber(page)
            except Exception, e:
                print e
                print "Couldn't get Hansard number for"
                print url
                print "Please enter: ",
                number = sys.stdin.readline().strip()
            try:
                hansard = Hansard.objects.get(session=session, number=number)
            except Hansard.DoesNotExist:
                hansard = Hansard(session=session, number=number, url=normurl)
                hansard.save()
            else:
                if hansard.url != normurl:
                    raise Exception("Hansard exists, with a different url: %s %s" % (normurl, hansard.url))
            cache = HansardCache(hansard=hansard)
            cache.saveHTML(page)
            cache.save()
            return cache
    else:
        raise Exception("Either url/session or hansard are required")



class _parseTracker(object):
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
            t = t.replace('``', '"')
            t = t.replace("''", '"')
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
        
    def saveStatement(self, t):
        if t.hasText():
            if t['member_title']:
                statement = Statement(hansard=self.hansard, heading=t['heading'], topic=t['topic'], time=datetime.datetime.combine(self.date, t['timestamp']), member=t['member'], who=t['member_title'], text=t.getText(), sequence=self.statement_index)
                # time is datetime.datetime.combine(self.date, t['timestamp'])
                self.statement_index += 1
                self.statements.append(statement)
            else:
                print "WARNING: No title for %s" % t.getText()
            
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
        
class HansardParser1994(HansardParser):
    
    def __init__(self, hansard, html):
        
        for regex in STARTUP_RE_1994:
            html = re.sub(regex[0], regex[1], html)

        super(HansardParser1994, self).__init__(hansard, html)
    
    def parse(self):
        
        super(HansardParser1994, self).parse()

        # Initialize variables
        t = _parseTracker()
        members = []
        session = self.hansard.session
                
        # Get the date
        try:
            #c = self.soup.find('h1', align=re.compile(r'CENTER', re.I)).findNext(text='HOUSE OF COMMONS').findNext(('b', 'h4'))
            c = self.soup.find('h1').findNext(text=lambda x: x.string == 'HOUSE OF COMMONS' and x.parent.name == 'h1').findNext(('b', 'h4'))
        except AttributeError:
            # alternate page style
            c = self.soup.find('td', height=85).findNext(text=re.compile(r'^\s*OFFICIAL\s+REPORT\s+\(HANSARD\)\s*$')).findNext('h2', align='center')
        if c.string is None:
            raise ParseException("Couldn't navigate to date. %s" % c)
        self.date = datetime.datetime.strptime(c.string.strip(), "%A, %B %d, %Y").date()
        self.hansard.date = self.date
        self.hansard.save()  

        # And the time
        c = c.findNext(text=r_housemet)
        match = re.search(r_housemet, c.string)
        t.setNext('timestamp', self.houseTime(match.group(1), match.group(2)))
        
        # Move the pointer to the start
        c = c.next
    
        # And start the big loop
        while c is not None:

            if parsetools.isString(c):
                # It's a string
                if re.search(r_letter, c):
                    # And it contains words! Add it to the buffer
                    t.addText(c, blockquote=bool(c.parent.name=='blockquote' or c.parent.name=='small' or c.parent.name=='ul' or c.parent.parent.name=='ul' or c.parent.parent.name=='blockquote'))
            elif c.name == 'h2' and c.has_key('align') and c['align'].lower() == 'center':
                # Heading
                c = c.findNext(text=r_letter)
                
                #c = c.next
                #if not parsetools.isString(c): raise ParseException("Expecting string right after h2")
                t.setNext('heading', parsetools.titleIfNecessary(parsetools.tameWhitespace(c.string.strip())))
            
            elif (c.name == 'h3' and c.has_key('align') and c['align'].lower() == 'center') or (c.name == 'center' and (c.find('h3') or c.find('b'))):
                # Topic
                if c.find(text=r_letter):
                    c = c.find(text=r_letter)
                    if 'Division No.' in c.string:
                        # It's a vote
                        # Set a flag to ignore text till the next speaker
                        t.ignoreText(True)
                    t.setNext('topic', parsetools.titleIfNecessary(parsetools.tameWhitespace(c.string.strip())))
            elif c.name == 'h4':
                # Either asterisks or a vote (hopefully)
                if c.string is not None and 'Division' in c.string:
                    # It's a vote
                    # Set a flag to ignore text till the next speaker
                    t.ignoreText(True)
                if c.string == 'APPENDIX':
                    self.saveStatement(t)
                    break
                c = c.nextSibling.previous
            elif c.name == 'i':
                # Italics -- let's make sure it's inline formatting
                if t.hasText() and c.string is not None and parsetools.isString(c.next.next) and re.search(r_notspace, c.next.next):
                    t.appendToText(c.string, italic=True)
                    c = c.next.next
                    t.appendToText(c.string)
            elif c.name == 'h5' or c.name == 'center' or (c.name == 'p' and c.has_key('align') and c['align'] == 'center'):
                # A heading we don't care about (hopefully!)
                if c.nextSibling is not None:
                    c = c.nextSibling.previous
                else: 
                    c = c.next
            elif c.name == 'table':
                # We don't want tables, right?
                if c.find(text=r_division):
                    # It's a vote
                    t.ignoreText(True)
                if not c.find('small'):
                    if not t.ignoringText():
                        # It's not a vote, so print a debug message to make sure we're not discarding important stuff
                        if VERBOSE: print "WARNING: Extracting table %s" % c
                    if c.nextSibling:
                        c = c.nextSibling.previous
                    else:
                        c = c.next
            elif c.name == 'div':
                if c.has_key('class') and c['class'] == 'Footer':
                    # We're done!
                    self.saveStatement(t)
                    break
            elif (c.name == 'a' and ( c.find('img', src=r_time_glyph) or (c.has_key('name') and re.search(r_timeanchor, c['name'])) )) or (c.name == 'li' and parsetools.isString(c.next) and re.search(r_time_paren, c.next)) or (c.name == 'p' and c.find(text=r_time_paren) and not c.find(text=r_letterbutnotD)):
                # Various kinds of timestamps
                if c.name == 'a':
                    c = c.findNext(text=r_notspace)
                else:
                    c = c.find(text=r_time_optionalparen)
                match = re.search(r_time_optionalparen, c.string)
                if not match: raise ParseException("Couldn't match time in %s\n%s" (c, c.parent))
                t.setNext('timestamp', parsetools.time(hour=int(match.group(1)), minute=int(match.group(2))))
            elif c.name == 'a' and c.has_key('class') and c['class'] == 'toc':
                # TOC link
                c = c.next
            elif c.name == 'b':
                if c.find('a'):
                    # 1. It's a page number -- ignore
                    c = c.find('a').next
                elif c.string is not None and re.search(r_time_paren, c.string):
                    # 2. It's a timestamp
                    match = re.search(r_time_paren, c.string)
                    t.setNext('timestamp', parsetools.time(hour=int(match.group(1)), minute=int(match.group(2))))
                    c = c.next
                elif c.string is not None and re.search(r_honorific, c.string.strip()):
                    # 3. It's the name of a new speaker
                    # Save the current buffer
                    self.saveStatement(t)
                    
                    # And start wrangling. First, get the colon out
                    member = None
                    t['member_title'] = parsetools.tameWhitespace(c.string.strip())
                    if t['member_title'].endswith(':'):
                        t['member_title'] = t['member_title'][:-1]
                    # Then, get the honorific out
                    match = re.search(r_honorific, t['member_title'])
                    (honorific, who) = (match.group(1), match.group(2))
                    if re.search(r_notamember, honorific):
                        # It's the speaker or someone unidentified. Don't bother matching to a member ID.
                        pass
                    else:
                        partyname = None
                        if 'Mr.' in honorific:
                            gender = 'M'
                        elif 'Mrs.' in honorific or 'Ms.' in honorific or 'Miss' in honorific:
                            gender = 'F'
                        else:
                            gender = None
                        if '(' in who:
                            # We have a post or riding
                            match = re.search(r'^(.+?) \((.+)\)', who)
                            if not match:
                                raise ParseException("Couldn't parse title %s" % who)
                            (name, paren) = (match.group(1).strip(), match.group(2).strip())
                            if paren == 'None':
                                # Manually labelled to not match
                                t['member_title'].replace(' (None)', '')
                                c = c.next.next
                                continue
                            # See if there's a party name; if so, strip it out
                            match = re.search(r'^(.+), (.+)$', paren)
                            if match:
                                (paren, partyname) = (match.group(1).strip(), match.group(2))
                            if re.search(r_politicalpost, paren):
                                # It's a post, not a riding
                                riding = None
                            else:
                                try:
                                    riding = Riding.objects.getByName(paren)
                                except Riding.DoesNotExist:
                                    raise ParseException("WARNING: Could not find riding %s" % paren)
                                    riding = None
                        else:
                            name = who.strip()
                            riding = None
                        if ' ' not in name or (riding is None and '(' not in who):
                            # We think it's a backreference, because either
                            # (a) there's only a last name
                            # (b) there's no riding AND no title was provided
                            # Go through the list of recent speakers and try to match
                            for possible in members:
                                if name in possible['name']:
                                    #print "Backreference successful: %s %s %s" % (possible['name'], name, possible['member'])
                                    # A match!
                                    member = possible['member']
                                    # Probably. If we have a riding, let's double-check
                                    if riding is not None and riding != possible['riding']:
                                        if VERBOSE: print "WARNING: Name backref matched (%s, %s) but not riding (%s, %s)" % (name, possible['name'], riding, possible['riding'])
                                        member = None
                                    # Also double-check on gender
                                    elif gender is not None and possible['gender'] is not None and gender != possible['gender']:
                                        member = None
                                    else:
                                        break
                            if member is None:
                                # Last-ditch: try a match by name...
                                try:
                                    pol = Politician.objects.getByName(name, session=session)
                                    member = ElectedMember.objects.get(session=session, member=pol)
                                except (Politician.DoesNotExist, Politician.MultipleObjectsReturned):
                                    # and, finally, just by last name
                                    poss = ElectedMember.objects.filter(session=session, member__name_family__iexact=name)
                                    if riding:
                                        poss = poss.filter(riding=riding)
                                    if gender:
                                        poss = poss.filter(Q(member__gender=gender) | Q(member__gender=''))
                                    if len(poss) == 1:
                                        member = poss[0]
                                        if VERBOSE: print "WARNING: Last-name-only match for %s -- %s" % (name, member)
                                    else:
                                        raise ParseException( "WARNING: Backreference match failed for %s (%s)" % (name, t['member_title']) )
                        else:
                            # Try to do a straight match
                            try:
                                if riding is not None:
                                    pol = Politician.objects.getByName(name, riding=riding, session=session)
                                else:
                                    pol = Politician.objects.getByName(name, session=session)
                            except Politician.DoesNotExist:
                                pol = None
                                if riding is not None:
                                    # In case we're dealing with a renamed riding, try matching without the riding
                                    try:
                                        pol = Politician.objects.getByName(name, session=session)
                                    except Politician.DoesNotExist:
                                        # We'll raise the exception later
                                        pass
                                    else:
                                        if VERBOSE: print "WARNING: Forced match without riding for %s: %s" % (t['member_title'], pol)
                                if pol is None:
                                    raise ParseException("Couldn't match speaker: %s (%s)\nriding: %s" % (name, t['member_title'], riding))
                            except Politician.MultipleObjectsReturned:
                                # Our name match can't disambiguate properly.
                                if partyname:
                                    # See if we can go by party
                                    try:
                                        party = Party.objects.getByName(partyname)
                                        pol = Politician.objects.getByName(name, session=session, party=party)
                                    except Party.DoesNotExist:
                                        pass # we'll produce our own exception in a moment
                                if pol is None:
                                    raise ParseException("Couldn't disambiguate politician: %s" % name)
                            member = ElectedMember.objects.get(member=pol, session=session)
                            if riding is not None: riding = member.riding
                            # Save in the list for backreferences
                            members.insert(0, {'name':name, 'member':member, 'riding':riding, 'gender':gender})
                            # Save the gender if appropriate
                            if gender and pol.gender != gender and SAVE_GENDER:
                                if pol.gender != '':
                                    raise ParseException("Gender conflict! We say %s, database says %s for %s (pol: %s)." % (gender, pol.gender, t['member_title'], pol))
                                if VERBOSE: print "Saving gender (%s) for %s" % (gender, t['member_title'])
                                pol.gender = gender
                                pol.save()
                            
                        # Okay! We finally have our member!
                        t['member'] = member
                    c = c.next
                elif c.string is None and len(c.contents) == 0:
                    # an empty bold tag!
                    pass
                elif c.string == 'APPENDIX':
                    # We don't want the appendix -- finish up
                    self.saveStatement(t)
                    break
                elif hasattr(c.string, 'count') and 'Government House' in c.string:
                    # quoted letter, discard
                    c = c.next
                else:
                    raise ParseException("Unexplained boldness! %s\n**\n%s" % (c, c.parent))
            
            # Okay, so after that detour we're back at the indent level of the main for loop
            # We're also done with the possible tags we care about, so advance the cursor and loop back...
            c = c.next
        return self.statements
              
        
class HansardParser2009(HansardParser):
    
    def __init__(self, hansard, html):
        
        for regex in STARTUP_RE_2009:
            html = re.sub(regex[0], regex[1], html)

        super(HansardParser2009, self).__init__(hansard, html)
        
        for x in self.soup.findAll('a', 'deleteMe'):
            x.findParent('div').extract()
        
    def parse(self):
        
        super(HansardParser2009, self).parse()
        
        # Initialize variables
        t = _parseTracker()
        
        
        # Get the date
        c = self.soup.find(text='OFFICIAL REPORT (HANSARD)').findNext('h2')
        self.date = datetime.datetime.strptime(c.string.strip(), "%A, %B %d, %Y").date()
        self.hansard.date = self.date
        self.hansard.save()
        
        c = c.findNext(text=r_housemet)
        match = re.search(r_housemet, c.string)
        t['timestamp'] = self.houseTime(match.group(1), match.group(2))
        
        # Move the pointer to the start
        c = c.next
    
        # And start the big loop
        while c is not None:
        
            # It's a string
            if not hasattr(c, 'name'):
                pass
            # Heading
            elif c.name == 'h2':
                c = c.next
                if not parsetools.isString(c): raise ParseException("Expecting string right after h2")
                t.setNext('heading', parsetools.titleIfNecessary(parsetools.tameWhitespace(c.string.strip())))
            
            # Topic
            elif c.name == 'h3':
                top = c.find(text=r_letter)
                #if not parsetools.isString(c):
                    # check if it's an empty header
                #    if c.parent.find(text=r_letter):
                #        raise ParseException("Expecting string right after h3")
                if top is not None:
                    c = top
                    t.setNext('topic', parsetools.titleIfNecessary(parsetools.tameWhitespace(c.string.strip())))
            
            elif c.name == 'h4':
                if c.string == 'APPENDIX':
                    self.saveStatement(t)
                    print "Appendix reached -- we're done!"
                    break
            # Timestamp
            elif c.name == 'a' and c.has_key('name') and c['name'].startswith('T'):
                match = re.search(r'^T(\d\d)(\d\d)$', c['name'])
                if match:
                    t.setNext('timestamp', parsetools.time(hour=int(match.group(1)), minute=int(match.group(2))))
                else:
                    raise ParseException("Couldn't match time %s" % c.attrs['name'])
                
            # div -- the biggie
            elif c.name == 'div':
                origdiv = c
                if c.find('b'):
                    # We think it's a new speaker
                    # Save the current buffer
                    self.saveStatement(t)
                
                    c = c.find('b')
                    if c.find('a'):
                        # There's a link...
                        c = c.find('a')
                        match = re.search(r'ResourceType=Affiliation&ResourceID=(\d+)', c['href'])
                        if match and c.find(text=r_letter):
                            parlwebid = int(match.group(1))
                            # We have the parl ID. First, see if we already know this ID.
                            pol = Politician.objects.getByParlID(parlwebid, lookOnline=False)
                            if pol is None:
                                # We don't. Try to do a quick name match first (if flags say so)
                                if not GET_PARLID_ONLINE:
                                    who = c.next.string
                                    match = re.search(r_honorific, who)
                                    if match:
                                        polname = re.sub(r'\(.+\)', '', match.group(2)).strip()
                                        try:
                                            #print "Looking for %s..." % polname,
                                            pol = Politician.objects.getByName(polname, session=self.hansard.session)
                                            #print "found."
                                        except Politician.DoesNotExist:
                                            pass
                                        except Politician.MultipleObjectsReturned:
                                            pass
                                if pol is None:
                                    # Still no match. Go online...
                                    try:
                                        pol = Politician.objects.getByParlID(parlwebid, session=self.hansard.session)
                                    except Politician.DoesNotExist:
                                        print "WARNING: Couldn't find politician for ID %d" % parlwebid
                            if pol is not None: t['member'] = ElectedMember.objects.get(member=pol, session=self.hansard.session)
                    c = c.next
                    if not parsetools.isString(c): raise Exception("Expecting string in b for member name")
                    t['member_title'] = c.strip()
                    if t['member_title'].endswith(':'): # Remove colon in e.g. Some hon. members:
                        t['member_title'] = t['member_title'][:-1]
                    c.findParent('b').extract() # We've got the title, now get the rest of the paragraph
                    c = origdiv
                    t.addText(parsetools.getText(c))
                else:
                    # There should be text in here
                    if c.find('div'):
                        if c.find('div', 'Footer'):
                            # We're done!
                            self.saveStatement(t)
                            print "Footer div reached -- done!"
                            break
                        raise Exception("I wasn't expecting another div in here")
                    t.addText(parsetools.getText(c), blockquote=bool(c.find('small')))
                
            c = c.next
        return self.statements
                