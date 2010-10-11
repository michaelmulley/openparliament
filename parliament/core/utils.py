import urllib, urllib2
import re
import httplib2
import json
from functools import wraps

from django.db import models
from django.conf import settings
from django.core import urlresolvers
from django.core.mail import mail_admins
from django.http import HttpResponsePermanentRedirect

def postcode_to_edid(postcode):
    # First try Elections Canada
    postcode = postcode.replace(' ', '')
    try:
        #return postcode_to_edid_ec(postcode)
        return postcode_to_edid_webserv(postcode)
    except:
        return postcode_to_edid_htv(postcode)

def postcode_to_edid_htv(postcode):
    url = 'http://howdtheyvote.ca/api.php?' + urllib.urlencode({
        'call': 'findriding',
        'key': settings.PARLIAMENT_HTV_API_KEY,
        'house_id': 1,
        'postal_code': postcode
    })
    try:
        response = urllib2.urlopen(url)
    except urllib2.URLError:
        return None
    match = re.search(r'<edid>(\d+)</edid>', response.read())
    if match:
        return int(match.group(1))
    return None
    
EC_POSTCODE_URL = 'http://elections.ca/scripts/pss/FindED.aspx?L=e&PC=%s'
r_ec_edid = re.compile(r'&ED=(\d{5})&')
def postcode_to_edid_ec(postcode):
    h = httplib2.Http(timeout=1)
    h.follow_redirects = False
    (response, content) = h.request(EC_POSTCODE_URL % postcode.replace(' ', ''))
    match = r_ec_edid.search(response['location'])
    return int(match.group(1))
    
def postcode_to_edid_webserv(postcode):
    try:
        response = urllib2.urlopen('http://postal-code-to-edid-webservice.heroku.com/postal_codes/' + postcode)
    except urllib2.HTTPError as e:
        if e.code == 404:
            return None
        raise e
    codelist = json.load(response)
    if not isinstance(codelist, list):
        mail_admins("Invalid response from postcode service", repr(codelist))
        raise Exception()
    if len(codelist) > 1:
        mail_admins("Multiple results for postcode", postcode + repr(codelist))
        return None
    return int(codelist[0])
    
def memoize_property(target):
    """Caches the result of a method that takes no arguments."""
    
    cacheattr = '_cache_' + target.__name__
    
    @wraps(target)
    def wrapped(self):
        if not hasattr(self, cacheattr):
            setattr(self, cacheattr, target(self))
        return getattr(self, cacheattr)
    return wrapped
    
def redir_view(view):
    """Function factory to redirect requests to the given view."""
    
    def wrapped(request, *args, **kwargs):
        return HttpResponsePermanentRedirect(
            urlresolvers.reverse(view, args=args, kwargs=kwargs)
        )
    return wrapped
    
def get_twitter_share_url(url, description, add_plug=True):
    """Returns a URL for a Twitter post page, prepopulated with a sharing message.
    
    url -- URL to the shared page -- should start with / and not include the domain
    description -- suggested content for sharing message
    add_plug -- if True, will add a mention of openparliament.ca, if there's room """
    
    PLUG = ' (from openparliament.ca)'
    
    longurl = settings.SITE_URL + url
    
    try:
        shorten_resp_raw = urllib2.urlopen(settings.BITLY_API_URL + urllib.urlencode({'longurl': longurl}))
        shorten_resp = json.load(shorten_resp_raw)
        shorturl = shorten_resp['data']['url']
    except Exception, e:
        # FIXME logging
        shorturl = longurl
    
    if (len(description) + len(shorturl)) > 139:
        description = description[:136-len(shorturl)] + '...'
    elif add_plug and (len(description) + len(shorturl) + len(PLUG)) < 140:
        description += PLUG
    message = "%s %s" % (description, shorturl)
    return 'http://twitter.com/home?' + urllib.urlencode({'status': message})
        
class ActiveManager(models.Manager):

    def get_query_set(self):
        return super(ActiveManager, self).get_query_set().filter(active=True)