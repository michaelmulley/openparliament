import datetime
import logging
import time

from django.conf import settings
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

# Items per e-mail; beyond this, the e-mail links to the full list
ALERT_MAX_ITEMS = 25


class Command(BaseCommand):
    help = "E-mails the alert matches recorded (by consume_indexing_queue) since the last run."

    def handle(self, **options):

        if getattr(settings, 'PARLIAMENT_SEARCH_CLOSED', False):
            return logger.error("Not sending alerts because of PARLIAMENT_SEARCH_CLOSED")

        from parliament.alerts.models import Topic, TopicMatch

        start_time = time.time()
        topic_ids = TopicMatch.objects.filter(sent__isnull=True).values_list('topic_id', flat=True).distinct()

        topics_sent = messages_sent = 0

        for topic in Topic.objects.filter(id__in=topic_ids):
            pending = list(topic.matches.filter(sent__isnull=True).order_by('-date', '-id'))
            subscriptions = list(topic.subscription_set.filter(
                active=True, user__email_bouncing=False).select_related('user'))
            now = datetime.datetime.now()

            if subscriptions:
                shown = pending[:ALERT_MAX_ITEMS]
                documents = topic.get_documents(shown)
                logger.debug('%s documents for query %s' % (len(documents), topic))
                if documents:
                    topics_sent += 1
                    for sub in subscriptions:
                        messages_sent += 1
                        sub.send_email(documents, more=len(pending) - len(shown))

            TopicMatch.objects.filter(id__in=[m.id for m in pending]).update(sent=now)
            topic.last_checked = now
            topic.save(update_fields=['last_checked'])

        if topics_sent:
            print("%s topics, %s subscriptions sent in %s seconds" % (
                topics_sent, messages_sent, (time.time() - start_time)))
