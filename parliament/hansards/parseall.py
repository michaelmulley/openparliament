from parliament.hansards.models import Hansard, HansardCache
from parliament.imports import hans
from django.db.models import Count
import sys, os
reload(sys)
sys.setdefaultencoding('utf8')
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0) # unbuffered stdout

for hansard in Hansard.objects.all().annotate(scount=Count('statement')).exclude(scount__gt=0).order_by('?'):
    try:
        print "Trying %d %s... " % (hansard.id, hansard)
        hans.parseAndSave(hansard)
        print "SUCCESS for %s" % hansard
    except Exception, e:
        cache = HansardCache.objects.get(hansard=hansard.id)
        print "******* FAILURE **********"
        print "HANSARD %d: %s" % (cache.hansard.id, cache.hansard)
        print "FILE: %s" % cache.filename
        print "URL: %s" % cache.hansard.url
        print "ERROR: %s" % e
        