import time

from django.db import transaction, models
from django.conf import settings

from parliament.politicians import twit
from parliament.politicians import googlenews as gnews
from parliament.imports import parlvotes, legisinfo, hans
from parliament.core.models import Politician, Session
from parliament.core import datautil
from django.core.mail import mail_admins
from parliament.hansards.models import Hansard
from parliament.activity import utils as activityutils
from parliament.alerts import utils as alertutils
from parliament.activity.models import Activity

@transaction.commit_on_success
def twitter():
    twit.save_tweets()
    return True
    
def googlenews():
    for pol in Politician.objects.current():
        gnews.save_politician_news(pol)
        #time.sleep(1)
        
def votes():
    parlvotes.import_votes()
    
@transaction.commit_on_success
def bills():
    legisinfo.import_bills(Session.objects.current())
    return True
    
def billstatus(private_members_also=False):
    legisinfo.update_statuses_for_session(Session.objects.current(), private_members_also=private_members_also)
    
def billstatus_full():
    billstatus(True)

@transaction.commit_on_success
def prune_activities():
    for pol in Politician.objects.current():
        activityutils.prune(Activity.objects.filter(politician=pol))
    return True
    
@transaction.commit_on_success
def hansards_load():
    datautil.hansards_from_calendar()
    return True
        
@transaction.commit_manually
def hansards_parse():
    for hansard in Hansard.objects.all().annotate(scount=models.Count('statement')).exclude(scount__gt=0).order_by('date').iterator():
        try:
            hans.parseAndSave(hansard)
        except Exception, e:
            transaction.rollback()
            mail_admins("Hansard parse failure on #%s" % hansard.id, unicode(e))
            continue
        else:
            transaction.commit()
        # now reload the Hansard to get the date
        hansard = Hansard.objects.get(pk=hansard.id)
        try:
            hansard.save_activity()
        except Exception, e:
            transaction.rollback()
            raise e
        else:
            transaction.commit()
        if getattr(settings, 'PARLIAMENT_SEND_EMAIL', True):
            alertutils.alerts_for_hansard(hansard)
            
def hansards():
    hansards_load()
    hansards_parse()