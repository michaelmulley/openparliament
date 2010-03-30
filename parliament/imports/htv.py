"""Various imports from the howdtheyvote.ca API.

Imports now exist to get all this data from the official Parliament site instead."""

from mulley.parliament.models import *
import urllib, urllib2
from xml.etree.ElementTree import ElementTree
import re, datetime
import decimal
from BeautifulSoup import BeautifulSoup
from django.db import transaction
from mulley.parliament import parsetools

def htv_getSessions (house=1):
    url = 'http://howdtheyvote.ca/api.php?call=getsessions&house_id=%d' % house
    apixml = urllib2.urlopen(url)
    apitree = ElementTree()
    apitree.parse(apixml)
    for session in apitree.findall('sessions/session'):
        id = int(session.findtext('session_id'))
        try:
            sessobj = Session.objects.get(pk=id)
        except Session.DoesNotExist:
            sessobj = Session(id=id)
        else:
            # already exists
            continue
        sessobj.name = session.findtext('name')
        sessobj.start = session.findtext('start')
        sessobj.end = parsetools.munge_date(session.findtext('end'))
        sessobj.save()
        
def htv_getHansards(session):
    url = 'http://www.howdtheyvote.ca/api.php?call=gethansards&session_id=%d' % session.id
    apixml = urllib2.urlopen(url)
    apitree = ElementTree()
    apitree.parse(apixml)
    for hansardx in apitree.findall('hansards/hansard'):
        id = int(hansardx.findtext('hansard_id'))
        try:
            hansardo = Hansard.objects.get(pk=id)
        except Hansard.DoesNotExist:
            hansardo = Hansard(id=id, session=session)
            hansardo.date = hansardx.findtext('hansard_date')
            hansardo.number = hansardx.findtext('hansard_number')
            hansardo.url = hansardx.findtext('url')
            hansardo.save()
        else:
            if hansardo.number != hansardx.findtext('hansard_number'):
                print "WARNING: Hansard id %d exists, but numbers don't match(%d, %s)" % (id, hansardo.number, hansardx.findtext('hansard_number'))

def htv_getMembers(session):
    url = 'http://howdtheyvote.ca/api.php?call=getmembers&session_id=%d' % session.id
    apixml = urllib2.urlopen(url)
    apitree = ElementTree()
    apitree.parse(apixml)
    for memberx in apitree.findall('members/member'):
        
        # The Member object
        id = int(memberx.findtext('member_id'))
        try:
            membero = Politician.objects.get(pk=id)
        except Politician.DoesNotExist:
            membero = Politician(id=id)
            membero.name = memberx.findtext('name')
            membero.name_given = memberx.findtext('name_first')
            membero.name_family = memberx.findtext('name_last')
            membero.dob = parsetools.munge_date(memberx.findtext('birth'))
            membero.site = memberx.findtext('website')
            membero.parlpage = memberx.findtext('website_official')
            membero.gender = memberx.findtext('gender')
            membero.save()
        else:
            if membero.name != memberx.findtext('name'):
                print "WARNING: Member ID %d exists, named %s not %s" % (id, membero.name, memberx.findtext('name'))
                # FIXME debug warning system
                continue

        # The Riding object
        edid = int(memberx.findtext('edid'))
        try:
            riding = Riding.objects.get(pk=edid)
        except Riding.DoesNotExist:
            riding = Riding(id=edid)
            riding.name = memberx.findtext('riding')
            riding.province = memberx.findtext('province')
            riding.save()
        else:
            if riding.name != memberx.findtext('riding'):
                print "WARNING: Riding ID %d exists, named %s not %x" % (edid, riding.name, memberx.findtext('riding'))
                continue
                
        # The Party object
        partyname = memberx.findtext('party')
        try:
            party = Party.objects.get(slug=partyname)
        except Party.DoesNotExist:
            party = Party(name=partyname, slug=partyname)
            party.save()
        
        try:
            emember = ElectedMember.objects.get(session=session, member=membero, riding=riding)
        except ElectedMember.DoesNotExist:
            ElectedMember(session=session, member=membero, riding=riding, party=party).save()
            
def htv_getStatements(hansard):
    url = 'http://howdtheyvote.ca/api.php?call=getquotes&hansard_id=%d' % hansard.id
    apixml = urllib2.urlopen(url)
    apitree = ElementTree()
    apitree.parse(apixml)    
    for quote in apitree.findall('quotes/quote'):
        id = int(quote.findtext('quote_id'))
        try:
            statement = Statement.objects.get(pk=id)
        except Statement.DoesNotExist:
            statement = Statement(id=id, hansard=hansard)
            statement.time = parsetools.munge_time(quote.findtext('time'))
            statement.heading = quote.findtext('heading')
            statement.topic = quote.findtext('topic')
            statement.who = quote.findtext('title')
            memid = parsetools.munge_int(quote.findtext('member_id'))
            if memid:
                try:
                    member = Politician.objects.get(pk=memid)
                except Politician.DoesNotExist:
                    print "WARNING: In quote #%d, couldn't find member #%d (%s)" % (id, memid, statement.who)
                else:
                    statement.member = member
            statement.text = quote.findtext('text')
            statement.htv_url = quote.findtext('url')
            statement.save()
        else:
            if statement.hansard.id != int(quote.findtext('hansard_id')):
                print "WARNING: Statement ID %d exists, but Hansard IDs differ."
            if statement.text != quote.findtext('text'):
                print "WARNING: Statement ID %d exists, but text differs:\n%s\n*********\n%s" % (id, statement.text, quote.findtext('text'))