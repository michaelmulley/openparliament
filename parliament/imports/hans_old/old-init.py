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
import pdb

from BeautifulSoup import BeautifulSoup, Comment, NavigableString
from django.db.models import Q
from django.db import transaction

from parliament.core.models import *
from parliament.hansards.models import Statement, HansardCache
from parliament.hansards.models import Document as Hansard
from parliament.core import parsetools
from parliament.imports.hans_old import current, old

def qp(id):
    """Utility quick-parse function. Takes a Hansard ID"""
    return parseAndSave(Document.objects.get(pk=id))
    
def soup(id):
    cache = loadHansard(Hansard.objects.get(pk=id))
    parser = _getParser(cache.hansard, cache.getHTML())
    return parser.soup
    
def _getParser(hansard, html):
    if hansard.session.start.year < 2006:
        return old.HansardParser1994(hansard, html)
    else:
        return current.HansardParser2009(hansard, html)

@transaction.commit_on_success
def parseAndSave(arg, auto_reparse=None):
    if isinstance(arg, Hansard):
        cache = loadHansard(arg)
    elif isinstance(arg, HansardCache):
        cache = arg
    else:
        raise Exception("Invalid argument to parseAndSave")
        
    if Statement.objects.filter(hansard=cache.hansard).count() > 0:
        if not auto_reparse:
            print "There are already Statements for %s." % cache.hansard
            print "Delete them? (y/n) ",
            yn = sys.stdin.readline().strip()
            if yn != 'y':
                return False
        for statement in Statement.objects.filter(hansard=cache.hansard):
            statement.delete()
    
    parser = _getParser(cache.hansard, cache.getHTML())
    
    statements = parser.parse()
    for statement in statements:
        #try:
        statement.save()
        statement.save_relationships()
        #except Exception, e:
        #    print "Error saving statement: %s %s" % (statement.sequence, statement.who)
        #    raise e 
    return True

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
            
def hansards_from_calendar(session=None):
    if not session:
        session = Session.objects.current()
    SKIP_HANSARDS = {
    'http://www2.parl.gc.ca/HousePublications/Publication.aspx?Language=E&Mode=2&Parl=36&Ses=2&DocId=2332160' : True,
    }
    url = 'http://www2.parl.gc.ca/housechamberbusiness/chambersittings.aspx?View=H&Parl=%d&Ses=%d&Language=E&Mode=2' % (session.parliamentnum, session.sessnum)
    #print "Getting calendar..."
    soup = BeautifulSoup(urllib2.urlopen(url))
    #print "Calendar retrieved."
    cal = soup.find('div', id='ctl00_PageContent_calTextCalendar')
    for link in cal.findAll('a', href=True):
        hurl = 'http://www2.parl.gc.ca' + link['href']
        if hurl in SKIP_HANSARDS:
            continue
        hurl = hurl.replace('Mode=2&', 'Mode=1&')
        #print "Loading url %s" % hurl
        try:
            loadHansard(url=hurl, session=session)
        except Exception, e:
            print "Failure on %s: %s" % (hurl, e)            
            
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
            #try:
            number = _getHansardNumber(page)
            #except Exception, e:
            #    print e
            #    print "Couldn't get Hansard number for"
            #    print url
            #    print "Please enter: ",
            #    number = sys.stdin.readline().strip()
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