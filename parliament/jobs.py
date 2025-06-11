import datetime
import time

from django.db import transaction, models
from django.conf import settings

from parliament.imports import parlvotes, legisinfo, parl_document, parl_cmte
from parliament.imports.mps import update_mps_from_ourcommons
from parliament.core.models import Politician, Session
from parliament.hansards.models import Document
from parliament.activity import utils as activityutils
from parliament.activity.models import Activity
from parliament.text_analysis import corpora
from parliament.summaries.generation import update_hansard_summaries, update_reading_summaries

import logging
logger = logging.getLogger(__name__)

mps = update_mps_from_ourcommons
        
def votes():
    parlvotes.import_votes()
    
def bills():
    legisinfo.import_bills(Session.objects.current())

@transaction.atomic
def prune_activities():
    for pol in Politician.objects.current():
        activityutils.prune(Activity.public.filter(politician=pol))
    return True

def committee_evidence():
    for document in Document.evidence\
      .annotate(scount=models.Count('statement'))\
      .exclude(scount__gt=0).exclude(skip_parsing=True).order_by('date').iterator():
        try:
            print(document)
            parl_document.import_document(document, allow_reimport=False)
            if document.statement_set.all().count():
                document.save_activity()
        except Exception as e:
            logger.exception("Evidence parse failure on #%s: %r" % (document.id, e))
            continue
    
def committees(sess=None):
    if sess is None:
        sess = Session.objects.current()
        if sess.start >= datetime.date.today():
            return
    try:
        parl_cmte.import_committee_list(session=sess)
    except Exception as e:
        logger.exception("Committee list import failure")
    parl_cmte.import_committee_documents(sess)

def committees_full():
    committees()
    committee_evidence()
    
@transaction.atomic
def hansards_load():
    parl_document.fetch_latest_debates()
        
def hansards_parse():
    for hansard in Document.objects.filter(document_type=Document.DEBATE)\
      .annotate(scount=models.Count('statement'))\
      .exclude(scount__gt=0).exclude(skip_parsing=True).order_by('date').iterator():
        with transaction.atomic():
            try:
                with transaction.atomic():
                    parl_document.import_document(hansard, allow_reimport=False)
            except Exception as e:
                logger.exception("Hansard parse failure on #%s: %r" % (hansard.id, e))
                continue
            # now reload the Hansard to get the date
            hansard = Document.objects.get(pk=hansard.id)
            hansard.save_activity()
            
def hansards():
    hansards_load()
    hansards_parse()

def reimport():
    parl_document.reimport_recent_documents()
    
def corpus_for_debates():
    corpora.generate_for_debates()

def corpus_for_committees():
    corpora.generate_for_committees()

def summaries():
    update_hansard_summaries()
    update_reading_summaries(Session.objects.current())
