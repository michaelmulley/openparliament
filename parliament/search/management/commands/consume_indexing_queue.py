import itertools
import logging

from django.core.management.base import BaseCommand

from parliament.search.index import index_objects
from parliament.search.solr import get_pysolr_instance

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

        solr = get_pysolr_instance()

        if update_tasks:
            update_objs = [t.content_object for t in update_tasks if t.content_object]

            index_objects(update_objs)

            IndexingTask.objects.filter(id__in=[t.id for t in update_tasks]).delete()

        if delete_tasks:
            delete_ids = [dt.identifier for dt in delete_tasks]
            # print(f"Deleting {len(delete_ids)} items from Solr")
            solr.delete(id=delete_ids, commit=False)
            solr.commit()

            IndexingTask.objects.filter(id__in=[t.id for t in delete_tasks]).delete()
