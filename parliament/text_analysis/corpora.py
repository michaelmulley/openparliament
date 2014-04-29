import datetime
import os.path
import cPickle as pickle
import re

from django.conf import settings

from parliament.text_analysis.frequencymodel import FrequencyModel

def _get_background_model_path(corpus_name, n):
    # Sanitize corpus_name, since it might be user input
    corpus_name = re.sub(r'[^a-z0-9-]', '', corpus_name) 
    return os.path.join(settings.PARLIAMENT_LANGUAGE_MODEL_PATH, '%s.%dgram' % (corpus_name, n))

def load_background_model(corpus_name, n):
    with open(_get_background_model_path(corpus_name, n), 'rb') as f:
        return pickle.load(f)

def generate_background_models(corpus_name, statements, ngram_lengths=[1,2,3]):
    for n in ngram_lengths:
        bg = FrequencyModel.from_statement_qs(statements, ngram=n, min_count=5 if n < 3 else 3)
        with open(_get_background_model_path(corpus_name, n), 'wb') as f:
            pickle.dump(bg, f, pickle.HIGHEST_PROTOCOL)

def generate_for_debates():
    from parliament.hansards.models import Statement
    since = datetime.datetime.now() - datetime.timedelta(days=365)
    qs = Statement.objects.filter(document__document_type='D', time__gte=since)
    generate_background_models('debates', qs)
    qs = Statement.objects.filter(time__gte=since)
    generate_background_models('default', qs)

def generate_for_old_debates():
    from parliament.hansards.models import Statement
    for year in range(1994, datetime.date.today().year):
        qs = Statement.objects.filter(document__document_type='D', time__year=year)
        generate_background_models('debates-%d' % year, qs)

def generate_for_committees():
    from parliament.hansards.models import Statement
    from parliament.committees.models import Committee, CommitteeMeeting
    from parliament.core.models import Session
    for committee in Committee.objects.filter(sessions=Session.objects.current()):
        since = datetime.date.today() - datetime.timedelta(days=365 * 3)
        document_ids = CommitteeMeeting.objects.filter(committee=committee, date__gte=since).values_list(
            'evidence_id', flat=True)
        qs = Statement.objects.filter(document__in=document_ids)
        generate_background_models(committee.slug, qs)

def generate_all():
    generate_for_debates()
    generate_for_committees()
    generate_for_old_debates()
