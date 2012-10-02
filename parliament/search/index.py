from django.conf import settings
from django.db.models import signals

from haystack import indexes
from haystack.utils import get_identifier

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
        from parliament.search.models import IndexingTask
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