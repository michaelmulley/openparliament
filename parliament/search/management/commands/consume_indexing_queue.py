import logging

from django.core.management.base import BaseCommand

from parliament.search.index import index_objects, delete_identifiers

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Runs any queued-up search indexing tasks."

    def handle(self, **options):

        from parliament.search.models import IndexingTask

        delete_tasks = list(
            IndexingTask.objects.filter(action='delete')
        )

        update_tasks = list(
            IndexingTask.objects.filter(action='update').prefetch_related('content_object')
        )

        if update_tasks:
            # The same object is often saved several times between runs;
            # index it once.
            update_objs = {}
            for t in update_tasks:
                if t.content_object:
                    update_objs.setdefault(t.identifier, t.content_object)

            index_objects(update_objs.values())

            IndexingTask.objects.filter(id__in=[t.id for t in update_tasks]).delete()

        if delete_tasks:
            delete_ids = set(dt.identifier for dt in delete_tasks)
            delete_identifiers(delete_ids)

            IndexingTask.objects.filter(id__in=[t.id for t in delete_tasks]).delete()
