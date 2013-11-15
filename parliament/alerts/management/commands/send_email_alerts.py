import logging
import time

from django.conf import settings
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Searches for new items & sends applicable email alerts."

    def handle(self, **options):

        if getattr(settings, 'PARLIAMENT_SEARCH_CLOSED', False):
            return logger.error("Not sending alerts because of PARLIAMENT_SEARCH_CLOSED")

        from parliament.alerts.models import Subscription

        start_time = time.time()

        subscriptions = Subscription.objects.filter(active=True, user__email_bouncing=False
            ).prefetch_related('user', 'topic')

        by_topic = {}
        for sub in subscriptions:
            by_topic.setdefault(sub.topic, []).append(sub)

        topics_sent = messages_sent = 0

        for topic, subs in by_topic.items():
            documents = topic.get_new_items()
            logger.debug(u'%s documents for query %s' % (len(documents), topic))
            #time.sleep(0.3)
            if documents:
                topics_sent += 1
                for sub in subs:
                    messages_sent += 1
                    sub.send_email(documents)

        if topics_sent:
            print "%s topics, %s subscriptions sent in %s seconds" % (
                topics_sent, messages_sent, (time.time() - start_time))
