from django.db.models import signals

from haystack import connections
from haystack.exceptions import NotHandled
from haystack.utils import get_identifier
from haystack.signals import BaseSignalProcessor

from parliament.search.models import IndexingTask


class QueuedIndexSignalProcessor(BaseSignalProcessor):

    def setup(self):
        signals.post_save.connect(self.enqueue_save)
        signals.post_delete.connect(self.enqueue_delete)

    def teardown(self):
        signals.post_save.disconnect(self.enqueue_save)
        signals.post_delete.disconnect(self.enqueue_delete)

    def enqueue_save(self, instance, **kwargs):
        return self.enqueue('update', instance)

    def enqueue_delete(self, instance, **kwargs):
        return self.enqueue('delete', instance)

    def enqueue(self, action, instance):
        try:
            connections['default'].get_unified_index().get_index(instance.__class__)
        except NotHandled:
            return False

        it = IndexingTask(
            action=action,
            identifier=get_identifier(instance)
        )
        if action == 'update':
            it.content_object = instance

        it.save()
