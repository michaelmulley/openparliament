import urllib, urllib2
import re
import httplib2
import json

from django.db import models
from django.conf import settings
from django.core.mail import mail_admins

def postcode_to_edid(postcode):
    # First try Elections Canada
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
    
def simple_function_cache(target):
    
    cacheattr = '_cache_' + target.__name__
    
    def wrapped(self):
        if not hasattr(self, cacheattr):
            setattr(self, cacheattr, target(self))
        return getattr(self, cacheattr)
    return wrapped
    
class memoize:
    """memoize(fn) - an instance which acts like fn but memoizes its arguments
       Will only work on functions with non-mutable arguments
    """
    def __init__(self, fn):
        self.fn = fn
        self.memo = {}
    
    def __call__(self, *args):
        if not self.memo.has_key(args):
            self.memo[args] = self.fn(*args)
        return self.memo[args]
        
class ActiveManager(models.Manager):

    def get_query_set(self):
        return super(ActiveManager, self).get_query_set().filter(active=True)