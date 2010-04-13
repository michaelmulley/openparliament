import urllib, urllib2
import re
import httplib2

def postcode_to_edid(postcode):
    # First try Elections Canada
    try:
        return postcode_to_edid_ec(postcode)
    except:
        return postcode_to_edid_htv(postcode)

HTV_API_KEY = 'JJLSGQVBFW'
def postcode_to_edid_htv(postcode):
    url = 'http://howdtheyvote.ca/api.php?' + urllib.urlencode({
        'call': 'findriding',
        'key': HTV_API_KEY,
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