import math
import urllib

from django.conf import settings
from django.db.models import signals
from django.utils.safestring import mark_safe

from haystack import indexes
from haystack.utils import get_identifier

from parliament.search.models import IndexingTask


class QueuedSearchIndex(indexes.SearchIndex):

    def _setup_save(self, model):
        signals.post_save.connect(self.enqueue_save, sender=model)

    def _setup_delete(self, model):
        signals.post_delete.connect(self.enqueue_delete, sender=model)

    def _teardown_save(self, model):
        signals.post_save.disconnect(self.enqueue_save, sender=model)

    def _teardown_delete(self, model):
        signals.post_delete.disconnect(self.enqueue_delete, sender=model)

    def enqueue_save(self, instance, **kwargs):
        return self.enqueue('update', instance)

    def enqueue_delete(self, instance, **kwargs):
        return self.enqueue('delete', instance)

    def enqueue(self, action, instance):
        it = IndexingTask(
            action=action,
            identifier=get_identifier(instance)
        )
        if action == 'update':
            it.content_object = instance

        it.save()

if getattr(settings, 'PARLIAMENT_AUTOUPDATE_SEARCH_INDEXES', False):
    SearchIndex = indexes.RealTimeSearchIndex
elif getattr(settings, 'PARLIAMENT_QUEUE_SEARCH_INDEXING', False):
    SearchIndex = QueuedSearchIndex
else:
    SearchIndex = indexes.SearchIndex


class SearchPaginator(object):
    """A dumb imitation of the Django Paginator."""

    def __init__(self, object_list, hits, pagenum, perpage,
            params, allowable_fields=None):
        self.object_list = object_list
        if pagenum > 1:
            self.has_previous = True
            self.previous_page_number = pagenum - 1
        else:
            self.has_previous = False
        self.hits = hits
        self.num_pages = int(math.ceil(float(self.hits) / float(perpage)))
        if pagenum < self.num_pages:
            self.has_next = True
            self.next_page_number = pagenum + 1
        self.number = pagenum
        self.start_index = ((pagenum - 1) * perpage) + 1
        self.end_index = self.start_index + perpage - 1
        if self.end_index > self.hits:
            self.end_index = self.hits

        if allowable_fields:
            good_params = dict([(k.encode('utf8'), v.encode('utf8')) for (k, v) in params.items() if k in allowable_fields])
        else:
            good_params = dict([(k.encode('utf8'), v.encode('utf8')) for (k, v) in params.items() if k not in ('page', 'partial')])
        self.querystring = mark_safe(urllib.urlencode(good_params))

    @property
    def paginator(self):
        return {'num_pages': self.num_pages, 'count': self.hits}
