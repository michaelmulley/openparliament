import json
import urllib
import urllib2
from functools import wraps

from django.db import models
from django.conf import settings
from django.core import urlresolvers
from django.http import HttpResponsePermanentRedirect

from compressor.filters import CompilerFilter

import logging
logger = logging.getLogger(__name__)


def memoize_property(target):
    """Caches the result of a method that takes no arguments."""
    
    cacheattr = '_cache_' + target.__name__
    
    @wraps(target)
    def wrapped(self):
        if not hasattr(self, cacheattr):
            setattr(self, cacheattr, target(self))
        return getattr(self, cacheattr)
    return wrapped

def language_property(fieldname):
    if settings.LANGUAGE_CODE.startswith('fr'):
        fieldname = fieldname + '_fr'
    else:
        fieldname = fieldname + '_en'

    return property(lambda self: getattr(self, fieldname))
    
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
    
#http://stackoverflow.com/questions/561486/how-to-convert-an-integer-to-the-shortest-url-safe-string-in-python
import string
ALPHABET = string.ascii_uppercase + string.ascii_lowercase + \
           string.digits + '-_'
ALPHABET_REVERSE = dict((c, i) for (i, c) in enumerate(ALPHABET))
BASE = len(ALPHABET)
SIGN_CHARACTER = '$'
def int64_encode(n):
    """Given integer n, returns a base64-ish string representation."""
    if n < 0:
        return SIGN_CHARACTER + int64_encode(-n)
    s = []
    while True:
        n, r = divmod(n, BASE)
        s.append(ALPHABET[r])
        if n == 0: break
    return ''.join(reversed(s))


def int64_decode(s):
    """Turns the output of int64_encode back into an integer"""
    if s[0] == SIGN_CHARACTER:
        return -int64_decode(s[1:])
    n = 0
    for c in s:
        n = n * BASE + ALPHABET_REVERSE[c]
    return n
        
class ActiveManager(models.Manager):

    def get_queryset(self):
        return super(ActiveManager, self).get_queryset().filter(active=True)

def feed_wrapper(feed_class):
    """Decorator that ensures django.contrib.syndication.Feed objects are created for
    each request, not reused over several requests. This means feed classes can safely
    store request-specific attributes on self."""
    def call_feed(request, *args, **kwargs):
        feed_instance = feed_class()
        feed_instance.request = request
        return feed_instance(request, *args, **kwargs)
    return call_feed

def lang_context(request):
    return {'fr': settings.LANGUAGE_CODE.startswith('fr')}

class AutoprefixerFilter(CompilerFilter):
    command = "{binary} {args} -o {outfile} {infile}"
    options = (
        ("binary", getattr(settings, "COMPRESS_AUTOPREFIXER_BINARY",
            './node_modules/.bin/postcss')),
        ("args", getattr(settings, "COMPRESS_AUTOPREFIXER_ARGS",
           '--use autoprefixer --autoprefixer.browsers "> 1%"')),
    )
