"""This *was* the parser for the current HTML format on parl.gc.ca.

But now we have XML. See parl_document.py.

This module is organized like so:
__init__.py - utility functions, simple parse interface
common.py - infrastructure used in the parsers, i.e. regexes
current.py - parser for the Hansard format used from 2006 to the present
old.py - (fairly crufty) parser for the format used from 1994 to 2006

"""
from parliament.imports.hans_old.common import *

import logging
logger = logging.getLogger(__name__)

class HansardParser2009(HansardParser):
    
    def __init__(self, hansard, html):
        
        for regex in STARTUP_RE_2009:
            html = re.sub(regex[0], regex[1], html)

        super(HansardParser2009, self).__init__(hansard, html)
        
        for x in self.soup.findAll('a', 'deleteMe'):
            x.findParent('div').extract()
            
    def process_related_link(self, tag, string, current_politician=None):
        #print "PROCESSING RELATED for %s" % string
        resid = re.search(r'ResourceID=(\d+)', tag['href'])
        restype = re.search(r'ResourceType=(Document|Affiliation)', tag['href'])
        if not resid and restype:
            return string
        resid, restype = int(resid.group(1)), restype.group(1)
        if restype == 'Document':
            try:
                bill = Bill.objects.get_by_legisinfo_id(resid)
            except Bill.DoesNotExist:
                match = re.search(r'\b[CS]\-\d+[A-E]?\b', string)
                if not match:
                    logger.error("Invalid bill link %s" % string)
                    return string
                bill = Bill.objects.create_temporary_bill(legisinfo_id=resid,
                    number=match.group(0), session=self.hansard.session)
            except Exception, e:
                print "Related bill search failed for callback %s" % resid
                print repr(e)
                return string
            return u'<bill id="%d" name="%s">%s</bill>' % (bill.id, escape(bill.name), string)
        elif restype == 'Affiliation':
            try:
                pol = Politician.objects.getByParlID(resid)
            except Politician.DoesNotExist:
                print "Related politician search failed for callback %s" % resid
                if getattr(settings, 'PARLIAMENT_LABEL_FAILED_CALLBACK', False):
                    # FIXME migrate away from internalxref?
                    InternalXref.objects.get_or_create(schema='pol_parlid', int_value=resid, target_id=-1)
                return string
            if pol == current_politician:
                return string # When someone mentions her riding, don't link back to her
            return u'<pol id="%d" name="%s">%s</pol>' % (pol.id, escape(pol.name), string)
    
    def get_text(self, cursor):
        text = u''
        for string in cursor.findAll(text=parsetools.r_hasText):
            if string.parent.name == 'a' and string.parent['class'] == 'WebOption':
                text += self.process_related_link(string.parent, string, self.t['politician'])
            else:
                text += unicode(string)
        return text
        
    def parse(self):
        
        super(HansardParser2009, self).parse()
        
        # Initialize variables
        t = ParseTracker()
        self.t = t
        member_refs = {}
        
        
        # Get the date
        c = self.soup.find(text='OFFICIAL REPORT (HANSARD)').findNext('h2')
        self.date = datetime.datetime.strptime(c.string.strip(), "%A, %B %d, %Y").date()
        self.hansard.date = self.date
        self.hansard.save()
        
        c = c.findNext(text=r_housemet)
        match = re.search(r_housemet, c.string)
        t['timestamp'] = self.houseTime(match.group(1), match.group(2))
        t.setNext('timestamp', t['timestamp'])
        
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
                    t['topic_set'] = True
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
                    t.setNext('timestamp', parsetools.time_to_datetime(
                        hour=int(match.group(1)),
                        minute=int(match.group(2)),
                        date=self.date))
                else:
                    raise ParseException("Couldn't match time %s" % c.attrs['name'])
                
            elif c.name == 'b' and c.string:
                # Something to do with written answers
                match = r_honorific.search(c.string)
                if match:
                    # It's a politician asking or answering a question
                    # We don't get a proper link here, so this has to be a name match
                    polname = re.sub(r'\(.+\)', '', match.group(2)).strip()
                    self.saveStatement(t)
                    t['member_title'] = c.string.strip()
                    t['written_question'] = True
                    try:
                        pol = Politician.objects.get_by_name(polname, session=self.hansard.session)
                        t['politician'] = pol
                        t['member'] = ElectedMember.objects.get_by_pol(politician=pol, date=self.date)
                    except Politician.DoesNotExist:
                        print "WARNING: No name match for %s" % polname
                    except Politician.MultipleObjectsReturned:
                        print "WARNING: Multiple pols for %s" % polname
                else:
                    if not c.string.startswith('Question'):
                        print "WARNING: Unexplained boldness: %s" % c.string
                
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
                                            pol = Politician.objects.get_by_name(polname, session=self.hansard.session)
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
                            if pol is not None:
                                t['member'] = ElectedMember.objects.get_by_pol(politician=pol, date=self.date)
                                t['politician'] = pol
                    c = c.next
                    if not parsetools.isString(c): raise Exception("Expecting string in b for member name")
                    t['member_title'] = c.strip()
                    #print c
                    if t['member_title'].endswith(':'): # Remove colon in e.g. Some hon. members:
                        t['member_title'] = t['member_title'][:-1]
                    
                    # Sometimes we don't get a link for short statements -- see if we can identify by backreference
                    if t['member']:
                        member_refs[t['member_title']] = t['member']
                        # Also save a backref w/o position/riding
                        member_refs[re.sub(r'\s*\(.+\)\s*', '', t['member_title'])] = t['member']
                    elif t['member_title'] in member_refs:
                        t['member'] = member_refs[t['member_title']]
                        t['politician'] = t['member'].politician
                    
                    c.findParent('b').extract() # We've got the title, now get the rest of the paragraph
                    c = origdiv
                    t.addText(self.get_text(c))
                else:
                    # There should be text in here
                    if c.find('div'):
                        if c.find('div', 'Footer'):
                            # We're done!
                            self.saveStatement(t)
                            print "Footer div reached -- done!"
                            break
                        raise Exception("I wasn't expecting another div in here")
                    txt = self.get_text(c).strip()
                    if r_proceedings.search(txt):
                        self.saveStatement(t)
                        self.saveProceedingsStatement(txt, t)
                    else:
                        t.addText(txt, blockquote=bool(c.find('small')))
            else:
                #print c.name
                if c.name == 'b':
                    print "B: ",
                    print c
                #if c.name == 'p':
                #    print "P: ",
                #    print c
                
            c = c.next
        return self.statements
