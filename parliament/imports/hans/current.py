"""Parser for the Hansard format used from 2006 to the present."""

from parliament.imports.hans.common import *

from django.utils.html import escape

from parliament.bills.models import Bill

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
                bill = Bill.objects.get_by_callback_id(resid)
            except Exception, e:
                print "Related bill search failed for callback %s" % resid
                print e
                return string
            return u'<bill id="%d" name="%s">%s</bill>' % (bill.id, escape(bill.name), string)
        elif restype == 'Affiliation':
            try:
                pol = Politician.objects.getByParlID(resid)
            except Politician.DoesNotExist:
                print "Related politician search failed for callback %s" % resid
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
                    t.addText(self.get_text(c), blockquote=bool(c.find('small')))
                
            c = c.next
        return self.statements
