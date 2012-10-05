import time

from django.db import transaction, models
from django.conf import settings

from parliament.politicians import twit
from parliament.politicians import googlenews as gnews
from parliament.imports import parlvotes, legisinfo, parl_document, parl_cmte
from parliament.core.models import Politician, Session
from parliament.hansards.models import Document
from parliament.activity import utils as activityutils
from parliament.activity.models import Activity

import logging
logger = logging.getLogger(__name__)

@transaction.commit_on_success
def twitter():
    twit.save_tweets()
    return True
    
def twitter_ids():
    from parliament.imports import politwitter
    politwitter.import_twitter_ids()
    
def googlenews():
    for pol in Politician.objects.current():
        gnews.save_politician_news(pol)
        #time.sleep(1)
        
def votes():
    parlvotes.import_votes()
    
def bills():
    legisinfo.import_bills(Session.objects.current())

@transaction.commit_on_success
def prune_activities():
    for pol in Politician.objects.current():
        activityutils.prune(Activity.public.filter(politician=pol))
    return True

def committee_evidence():
    for document in Document.evidence\
      .annotate(scount=models.Count('statement'))\
      .exclude(scount__gt=0).exclude(skip_parsing=True).order_by('date').iterator():
        print document
        parl_document.import_document(document, interactive=False)
        if document.statement_set.all().count():
            document.save_activity()
    
def committees(sess=None):
    if sess is None:
        sess = Session.objects.current()
    parl_cmte.import_committee_list(session=sess)
    parl_cmte.import_committee_documents(sess)

def committees_full():
    committees()
    committee_evidence()
    
@transaction.commit_on_success
def hansards_load():
    parl_document.fetch_latest_debates()
    return True
        
@transaction.commit_manually
def hansards_parse():
    for hansard in Document.objects.filter(document_type=Document.DEBATE)\
      .annotate(scount=models.Count('statement'))\
      .exclude(scount__gt=0).exclude(skip_parsing=True).order_by('date').iterator():
        try:
            parl_document.import_document(hansard, interactive=False)
        except Exception, e:
            transaction.rollback()
            logger.error("Hansard parse failure on #%s: %r" % (hansard.id, e))
            continue
        else:
            transaction.commit()
        # now reload the Hansard to get the date
        hansard = Document.objects.get(pk=hansard.id)
        try:
            hansard.save_activity()
        except Exception, e:
            transaction.rollback()
            raise e
        else:
            transaction.commit()
    transaction.commit()
            
def hansards():
    hansards_load()
    hansards_parse()
    
def wordcloud():
    # FIXME
    h = Document.objects.filter(document_type=Document.DEBATE)[0]
    h.get_wordoftheday()
    if not h.wordcloud:
        h.generate_wordcloud()