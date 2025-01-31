import itertools

from django.conf import settings
from django.db.models import signals

from parliament.search.models import IndexingTask
from parliament.search.solr import get_pysolr_instance

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

def get_content_type(model_obj) -> str:
    return f"{model_obj._meta.app_label}.{model_obj._meta.model_name}"

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
    d['django_id'] = obj.pk
    d['id'] = get_identifier(obj)
    return {k:v for k,v in d.items() if v is not None}

def index_model(model_cls):
    return index_qs(model_cls.search_get_qs())

def index_all():
    for model_cls in _search_model_registry:
        index_model(model_cls)

def index_qs(qs, batchsize=1000):
    batches = itertools.batched(qs.iterator(chunk_size=batchsize), batchsize)
    for i, batch in enumerate(batches):
        index_objects(batch)
        print(i * batchsize)

def index_objects(model_objs):
    prepared_objs = [get_search_dict(o)
                        for o in model_objs if o.search_should_index()]
    get_pysolr_instance().add(prepared_objs)


