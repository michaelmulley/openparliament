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
from parliament.imports.hans_old.common import *

r_bill = re.compile(r'[bB]ill C-(\d+)')
class HansardParser1994(HansardParser):
    
    def __init__(self, hansard, html):
        
        for regex in STARTUP_RE_1994:
            html = re.sub(regex[0], regex[1], html)

        super(HansardParser1994, self).__init__(hansard, html)
        
    def replace_bill_link(self, billmatch):
        billnumber = int(billmatch.group(1))
        try:
            bill = Bill.objects.get(sessions=self.hansard.session, number_only=billnumber)
        except Bill.DoesNotExist:
            #print "NO BILL FOUND for %s" % billmatch.group(0)
            return billmatch.group(0)
        result = u'<bill id="%d" name="%s">%s</bill>' % (bill.id, escape(bill.name), "Bill C-%s" % billnumber)
        #print "REPLACING %s with %s" % (billmatch.group(0), result)
        return result
    
    def label_bill_links(self, txt):
        return r_bill.sub(self.replace_bill_link, txt)
    
    def parse(self):
        
        super(HansardParser1994, self).parse()

        # Initialize variables
        t = ParseTracker()
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
        t['timestamp'] = self.houseTime(match.group(1), match.group(2))
        t.setNext('timestamp', t['timestamp'])
        
        # Move the pointer to the start
        c = c.next
    
        # And start the big loop
        while c is not None:

            if parsetools.isString(c):
                # It's a string
                if re.search(r_letter, c):
                    # And it contains words!
                    if r_proceedings.search(c):
                        # It's a "The House resumed" statement
                        self.saveStatement(t)
                        self.saveProceedingsStatement(c, t)
                    else:
                        # Add it to the buffer
                        txt = self.label_bill_links(c)
                        t.addText(txt, blockquote=bool(c.parent.name=='blockquote'
                                            or c.parent.name=='small'
                                            or c.parent.name=='ul'
                                            or c.parent.parent.name=='ul'
                                            or c.parent.parent.name=='blockquote'))
            
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
                                    riding = Riding.objects.get_by_name(paren)
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
                                    pol = Politician.objects.get_by_name(name, session=session)
                                    member = ElectedMember.objects.get_by_pol(politician=pol, date=self.date)
                                except (Politician.DoesNotExist, Politician.MultipleObjectsReturned):
                                    # and, finally, just by last name
                                    poss = ElectedMember.objects.filter(sessions=session, politician__name_family__iexact=name)
                                    if riding:
                                        poss = poss.filter(riding=riding)
                                    if gender:
                                        poss = poss.filter(Q(politician__gender=gender) | Q(politician__gender=''))
                                    if len(poss) == 1:
                                        member = poss[0]
                                        if VERBOSE: print "WARNING: Last-name-only match for %s -- %s" % (name, member)
                                    else:
                                        raise ParseException( "WARNING: Backreference match failed for %s (%s)" % (name, t['member_title']) )
                        else:
                            # Try to do a straight match
                            try:
                                if riding is not None:
                                    pol = Politician.objects.get_by_name(name, riding=riding, session=session)
                                else:
                                    pol = Politician.objects.get_by_name(name, session=session)
                            except Politician.DoesNotExist:
                                pol = None
                                if riding is not None:
                                    # In case we're dealing with a renamed riding, try matching without the riding
                                    try:
                                        pol = Politician.objects.get_by_name(name, session=session)
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
                                        party = Party.objects.get_by_name(partyname)
                                        pol = Politician.objects.get_by_name(name, session=session, party=party)
                                    except Party.DoesNotExist:
                                        pass # we'll produce our own exception in a moment
                                if pol is None:
                                    raise ParseException("Couldn't disambiguate politician: %s" % name)
                            member = ElectedMember.objects.get_by_pol(politician=pol, date=self.date)
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
                        t['politician'] = member.politician
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