import logging
import time

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError

from parliament.search import es_index
from parliament.search.index import get_search_models, index_model, index_qs

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """Builds a fresh Elasticsearch index from the database.

By default, a new index is created and loaded in the background while the
existing one keeps serving searches; then the alias is swapped to the new
index and the old one deleted. With --models, the given models are instead
re-indexed in place into the live index."""

    def add_arguments(self, parser):
        parser.add_argument('--models', help="Comma-separated app.model labels to reindex in place "
            "(e.g. hansards.statement,bills.bill). Without this, everything is rebuilt into a new index.")
        parser.add_argument('--since', help="With --models: only objects dated on or after this "
            "YYYY-MM-DD (statements by time, bills by introduction date).")
        parser.add_argument('--no-swap', action='store_true',
            help="Build the new index but leave the alias pointing at the old one.")
        parser.add_argument('--keep-old', action='store_true',
            help="Don't delete the previous index after swapping.")

    def handle(self, **options):
        client = es_index.get_es_client()
        start_time = time.time()

        def progress(model_label):
            def _progress(n):
                self.stdout.write(f"  {model_label}: {n} indexed ({time.time() - start_time:.0f}s)")
            return _progress

        if options['models']:
            models = [apps.get_model(label) for label in options['models'].split(',')]
            unregistered = [m for m in models if m not in get_search_models()]
            if unregistered:
                raise CommandError(f"Not registered for search: {unregistered}")
            for model in models:
                qs = model.search_get_qs()
                if options['since']:
                    date_field = {'hansards.statement': 'time', 'bills.bill': 'introduced'}.get(model._meta.label_lower)
                    if not date_field:
                        raise CommandError(f"--since not supported for {model._meta.label_lower}")
                    qs = qs.filter(**{f'{date_field}__gte': options['since']})
                self.stdout.write(f"Reindexing {model._meta.label_lower} in place"
                                  + (f" since {options['since']}" if options['since'] else ''))
                index_qs(qs, progress=progress(model._meta.label_lower))
            return

        new_index = es_index.new_index_name()
        self.stdout.write(f"Building {new_index}")
        es_index.create_index(new_index, client=client, bulk_load=True)
        try:
            for model in get_search_models():
                self.stdout.write(f"Indexing {model._meta.label_lower}")
                index_model(model, index=new_index, progress=progress(model._meta.label_lower))
            es_index.finish_bulk_load(new_index, client=client)
        except Exception:
            self.stderr.write(f"Failed; deleting {new_index}")
            client.indices.delete(index=new_index)
            raise

        count = client.count(index=new_index)['count']
        self.stdout.write(f"{new_index} built with {count} documents in {time.time() - start_time:.0f}s")

        if options['no_swap']:
            self.stdout.write(f"Alias {es_index.get_alias_name()} left unchanged")
            return

        old = es_index.swap_alias(new_index, client=client, delete_old=not options['keep_old'])
        self.stdout.write(f"Alias {es_index.get_alias_name()} -> {new_index}"
                          + (f" (replaced {', '.join(old)})" if old else ""))
