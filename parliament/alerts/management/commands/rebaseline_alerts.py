import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """Marks every alert topic's current search results as already seen,
without sending anything.

Run this once right after switching search backends (or otherwise changing
what a query matches), so that subscribers aren't emailed older items that the
new backend matches but the old one didn't. With --dry-run, only reports how
many items would have been treated as new: a useful measure of how much the
backends differ."""

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--verbose', action='store_true',
            help="List the items that would have been treated as new")

    def handle(self, **options):
        from parliament.alerts.models import Topic

        topics = Topic.objects.filter(subscription__active=True).distinct()
        topics_with_new = items_new = 0
        for topic in topics:
            documents = topic.get_new_items(label_as_seen=not options['dry_run'])
            if documents:
                topics_with_new += 1
                items_new += len(documents)
                if options['verbose']:
                    self.stdout.write(f"{topic.query}:")
                    for doc in documents:
                        self.stdout.write(f"    {doc['date']:%Y-%m-%d} {doc['url']}")
        verb = "would be" if options['dry_run'] else "were"
        self.stdout.write(f"{topics.count()} topics checked; {items_new} items in {topics_with_new} topics "
                          f"{verb} marked seen")
