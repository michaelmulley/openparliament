import datetime
import logging
import os
import tempfile

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from parliament.search.index import index_objects, delete_identifiers

logger = logging.getLogger(__name__)

# Processed tasks are kept this long so a standby that has been offline can
# still catch up by replaying them.
KEEP_PROCESSED_DAYS = 14


def collapse_tasks(tasks):
    """Reduce IndexingTasks (in the order they were created) to the final
    action for each identifier. The same object is often saved several times
    between runs, and an object updated then deleted should end up deleted.

    Returns (updates, deletes): updates maps identifier -> the last update task
    for it; deletes is the set of identifiers whose last action was a delete."""
    final = {}
    for t in tasks:
        final[t.identifier] = t
    updates = {ident: t for ident, t in final.items() if t.action == 'update'}
    deletes = {ident for ident, t in final.items() if t.action == 'delete'}
    return updates, deletes


def apply_tasks(tasks):
    """Apply a batch of IndexingTasks to the search index. Returns the
    identifiers that were (re)indexed. Update tasks whose object no longer
    exists are skipped; a delete task for it will follow."""
    updates, deletes = collapse_tasks(tasks)
    update_objs = {ident: t.content_object for ident, t in updates.items()
                   if t.content_object is not None}
    if update_objs:
        index_objects(update_objs.values())
    if deletes:
        delete_identifiers(deletes)
    return update_objs.keys()


class Command(BaseCommand):
    help = """Applies queued-up search indexing tasks to the search index.

On the primary (default): applies unprocessed tasks, matches what was indexed
against alert topics, marks the tasks processed, and prunes tasks processed
more than %d days ago. Tasks are marked rather than deleted so a standby can
replay them.

On a standby (--standby-cursor-file): the IndexingTask table arrives through
database replication. Every task after the id stored in the cursor file is
applied to the local search index, and the cursor advanced. Nothing is written
to the database and no alert matching is done.""" % KEEP_PROCESSED_DAYS

    def add_arguments(self, parser):
        parser.add_argument('--standby-cursor-file',
            help="Standby mode: file holding the id of the last IndexingTask applied.")
        parser.add_argument('--init-cursor', action='store_true',
            help="With --standby-cursor-file: apply nothing, just set the cursor to the "
                 "newest task. Run this immediately before a full rebuild_search_index.")

    def handle(self, **options):
        if options['standby_cursor_file']:
            self.handle_standby(options['standby_cursor_file'], options['init_cursor'])
        elif options['init_cursor']:
            raise CommandError("--init-cursor requires --standby-cursor-file")
        else:
            self.handle_primary()

    def handle_primary(self):
        from parliament.alerts.matching import record_matches
        from parliament.search.models import IndexingTask

        if getattr(settings, 'PARLIAMENT_DB_READONLY', False):
            raise CommandError("Database is read-only; on a standby use --standby-cursor-file")

        tasks = list(
            IndexingTask.objects.filter(processed__isnull=True)
            .order_by('id').prefetch_related('content_object')
        )

        if tasks:
            indexed = apply_tasks(tasks)

            # If this fails, the tasks stay queued and are retried (and the
            # objects harmlessly re-indexed) next time, rather than the
            # alerts silently missing them.
            if indexed:
                record_matches(indexed)

            IndexingTask.objects.filter(id__in=[t.id for t in tasks]).update(
                processed=timezone.now())

        IndexingTask.objects.filter(
            processed__lt=timezone.now() - datetime.timedelta(days=KEEP_PROCESSED_DAYS)
        ).delete()

    def handle_standby(self, cursor_file, init):
        from parliament.search.models import IndexingTask

        if not getattr(settings, 'PARLIAMENT_DB_READONLY', False):
            raise CommandError("--standby-cursor-file given but PARLIAMENT_DB_READONLY is not set; "
                               "this doesn't look like a standby.")

        if init:
            newest = IndexingTask.objects.order_by('-id').values_list('id', flat=True).first() or 0
            self._write_cursor(cursor_file, newest)
            self.stdout.write(f"Cursor set to {newest}")
            return

        try:
            with open(cursor_file) as f:
                cursor = int(f.read().strip())
        except (OSError, ValueError) as e:
            raise CommandError(f"Can't read cursor from {cursor_file} ({e}). Run with "
                               "--init-cursor, then rebuild_search_index, to start from scratch.")

        tasks = list(
            IndexingTask.objects.filter(id__gt=cursor)
            .order_by('id').prefetch_related('content_object')
        )
        if tasks:
            apply_tasks(tasks)
            self._write_cursor(cursor_file, tasks[-1].id)
            self.stdout.write(f"Applied {len(tasks)} tasks; cursor now {tasks[-1].id}")

    @staticmethod
    def _write_cursor(path, value):
        # Write atomically so a crash mid-write can't leave an empty cursor.
        d = os.path.dirname(path) or '.'
        fd, tmp = tempfile.mkstemp(dir=d, prefix='.cursor-')
        try:
            with os.fdopen(fd, 'w') as f:
                f.write(f"{value}\n")
            os.replace(tmp, path)
        except BaseException:
            os.unlink(tmp)
            raise
