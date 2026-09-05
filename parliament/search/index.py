import itertools
import logging

from django.conf import settings
from django.db.models import signals

from parliament.search import es_index
from parliament.search.models import IndexingTask

logger = logging.getLogger(__name__)

_search_model_registry = set()
def register_search_model(cls):
    """
    Register a model for indexing with the search engine.

    The model must implement the following methods:
    - search_dict() returns a dictionary of the object
            as it should be stored in the search engine
    - search_should_index() returns a boolean for whether the object should be indexed
    - search_get_qs() returns a queryset of all indexable objects
    """
    for required_fn in ['search_dict', 'search_should_index', 'search_get_qs']:
        if not hasattr(cls, required_fn):
            raise Exception(f"{cls} must implement {required_fn}")
    _search_model_registry.add(cls)
    return cls

def get_search_models():
    return sorted(_search_model_registry, key=get_content_type_for_model)

def get_content_type_for_model(model_cls) -> str:
    return f"{model_cls._meta.app_label}.{model_cls._meta.model_name}"

def get_content_type(model_obj) -> str:
    return get_content_type_for_model(model_obj._meta.model)

def get_identifier(model_obj) -> str:
    return f"{get_content_type(model_obj)}.{model_obj.pk}"

def _enqueue(action: str, instance):
    if instance._meta.model in _search_model_registry:
        it = IndexingTask(
            action=action,
            identifier=get_identifier(instance)
        )
        if action == 'update':
            it.content_object = instance

        it.save()

def save_handler(instance, **kwargs):
    return _enqueue('update', instance)

def delete_handler(instance, **kwargs):
    return _enqueue('delete', instance)

if getattr(settings, 'PARLIAMENT_TRACK_INDEXING_TASKS', False):
    signals.post_save.connect(save_handler)
    signals.post_delete.connect(delete_handler)
   
def get_search_dict(obj):
    d = obj.search_dict()
    d['django_ct'] = get_content_type(obj)
    d['django_id'] = str(obj.pk)
    d['id'] = get_identifier(obj)
    return {k:v for k,v in d.items() if v is not None}

def index_model(model_cls, index=None, progress=None):
    return index_qs(model_cls.search_get_qs(), index=index, progress=progress)

def index_all(index=None, progress=None):
    for model_cls in get_search_models():
        index_model(model_cls, index=index, progress=progress)

def index_qs(qs, batchsize=1000, index=None, progress=None):
    """Index every object in a queryset. `progress(n)` is called after each
    batch with the running count of objects processed."""
    total = 0
    batches = itertools.batched(qs.iterator(chunk_size=batchsize), batchsize)
    for batch in batches:
        index_objects(batch, index=index)
        total += len(batch)
        if progress:
            progress(total)
    return total

def index_objects(model_objs, index=None):
    prepared_objs = [get_search_dict(o)
                        for o in model_objs if o.search_should_index()]
    return es_index.index_documents(prepared_objs, index=index)

def delete_identifiers(identifiers):
    return es_index.delete_documents(identifiers)
