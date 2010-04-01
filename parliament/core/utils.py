import urllib, urllib2
import re

HTV_API_KEY = 'JJLSGQVBFW'
def postcode_to_edid(postcode):
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
    
def simple_function_cache(target):
    
    cacheattr = '_cache_' + target.__name__
    
    def wrapped(self):
        if not hasattr(self, cacheattr):
            setattr(self, cacheattr, target(self))
        return getattr(self, cacheattr)
    return wrapped