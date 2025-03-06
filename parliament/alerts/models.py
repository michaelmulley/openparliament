import base64
import datetime
import hashlib
import re
from smtplib import SMTPException
import time

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.signing import Signer
from django.urls import reverse
from django.db import models
from django.template import loader

from parliament.core.models import Politician
from parliament.core.templatetags.ours import english_list
from parliament.core.utils import ActiveManager
from parliament.search.solr import SearchQuery

import logging
logger = logging.getLogger(__name__)


class TopicManager(models.Manager):

    def get_or_create_by_query(self, query):
        query_obj = SearchQuery(query)
        if 'Date' in query_obj.filters:
            del query_obj.filters['Date']  # Date filters make no sense in alerts
        normalized_query = query_obj.normalized_query
        if not normalized_query:
            raise ValueError("Invalid query")
        return self.get_or_create(query=normalized_query)


class Topic(models.Model):
    """A search that one or more people have saved."""
    query = models.CharField(max_length=800, unique=True)
    created = models.DateTimeField(default=datetime.datetime.now)
    last_checked = models.DateTimeField(blank=True, null=True)
    last_found = models.DateTimeField(blank=True, null=True)

    objects = TopicManager()

    def __str__(self):
        if self.politician_hansard_alert:
            return '%s in House debates' % self.person_name
        return self.query

    def save(self, *args, **kwargs):
        super(Topic, self).save(*args, **kwargs)
        self.initialize_if_necessary()

    def get_search_query(self, limit=25):
        query_obj = SearchQuery(self.query, limit=limit,
            user_params={'sort': 'date desc'},
            full_text=self.politician_hansard_alert,
            solr_params={
                'mm': '100%' # match all query terms
            })

        # Only look for items newer than 60 days
        today = datetime.date.today()
        past = today - datetime.timedelta(days=60)
        query_obj.filters['Date'] = '%d-%02d to %d-12' % (
            past.year,
            past.month,
            today.year)

        return query_obj

    def initialize_if_necessary(self):
        if (not self.last_checked) or (
                (datetime.datetime.now() - self.last_checked) > datetime.timedelta(hours=24)):
            self.get_new_items(limit=40)

    def get_new_items(self, label_as_seen=True, limit=25):
        query_obj = self.get_search_query(limit=limit)
        result_ids = set((result['url'] for result in query_obj.documents))
        if result_ids:
            ids_seen = set(
                SeenItem.objects.filter(topic=self, item_id__in=list(result_ids))
                    .values_list('item_id', flat=True)
            )
            result_ids -= ids_seen

        self.last_checked = datetime.datetime.now()
        if result_ids:
            self.last_found = datetime.datetime.now()
        self.save()

        if label_as_seen and result_ids:
            SeenItem.objects.bulk_create([
                SeenItem(topic=self, item_id=result_id)
                for result_id in result_ids
            ])

        items = [r for r in reversed(query_obj.documents) if r['url'] in result_ids]

        if self.politician_hansard_alert:
            # Remove procedural stuff by the Speaker
            items = [r for r in items
                if 'Speaker' not in r['politician'] or len(r['full_text']) > 1200]

        return items

    @property
    def politician_hansard_alert(self):
        """Is this an alert for everything an MP says in the House chamber?"""
        return bool(re.search(r'^MP: \S+ Type: "debate"$', self.query))

    @property
    def person_name(self):
        match = re.search(r'Person: "([^"]+)"', self.query)
        if match:
            return match.group(1)
        match = re.search(r'MP: "([^\s"]+)"', self.query)
        if match:
            return Politician.objects.get_by_slug_or_id(match.group(1)).name


class SeenItem(models.Model):
    """A record that users have already seen a given item for a topic."""
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
    item_id = models.CharField(max_length=400, db_index=True)
    timestamp = models.DateTimeField(default=datetime.datetime.now)

    class Meta:
        unique_together = [
            ('topic', 'item_id')
        ]

    def __str__(self):
        return '%s seen for %s' % (self.item_id, self.topic)


class SubscriptionManager(models.Manager):

    def get_or_create_by_query(self, query, user):
        topic, created = Topic.objects.get_or_create_by_query(query)
        return self.get_or_create(topic=topic, user=user)


class Subscription(models.Model):
    """A specific user's alert subscription for a specific search."""
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE)

    created = models.DateTimeField(default=datetime.datetime.now)
    active = models.BooleanField(default=True)
    last_sent = models.DateTimeField(blank=True, null=True)

    objects = SubscriptionManager()

    class Meta:
        unique_together = [
            ('topic', 'user')
        ]
        ordering = ['-created']

    def __str__(self):
        return '%s: %s' % (self.user, self.topic)

    def save(self, *args, **kwargs):
        new = not self.id
        super(Subscription, self).save(*args, **kwargs)
        if new:
            self.topic.initialize_if_necessary()

    def get_unsubscribe_url(self, full=False):
        key = Signer(salt='alerts_unsubscribe').sign(str(self.id))
        return (settings.SITE_URL if full else '') + reverse(
            'alerts_unsubscribe', kwargs={'key': key})

    def render_message(self, documents):
        ctx = {
            'documents': documents,
            'unsubscribe_url': self.get_unsubscribe_url(full=True)
        }

        if self.topic.politician_hansard_alert:
            ctx['person_name'] = documents[0]['politician']
            t = loader.get_template('alerts/mp_hansard_alert.txt')
            text = t.render(ctx)
            return dict(text=text)

        ctx.update(
            topic=self.topic
        )
        t = loader.get_template('alerts/search_alert.txt')
        text = t.render(ctx)
        return dict(text=text)

    def get_subject_line(self, documents):
        if self.topic.politician_hansard_alert:
            topics = set((d['topic'] for d in documents if 'topic' in d))
            if topics:
                subj = '%(politician)s spoke about %(topics)s in the House' % {
                    'politician': documents[0]['politician'],
                    'topics': english_list(list(topics))
                }
            else:
                subj = documents[0]['politician'] + ' spoke in the House'
        else:
            subj = 'New from openparliament.ca for %s' % self.topic.query
        return subj[:200]

    def send_email(self, documents):
        rendered = self.render_message(documents)
        msg = EmailMultiAlternatives(
            self.get_subject_line(documents),
            rendered['text'],
            '"openparliament.ca alerts" <alerts@contact.openparliament.ca>',
            [self.user.email],
            headers={
                'List-Unsubscribe': '<' + self.get_unsubscribe_url(full=True) + '>',
                'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click'
            }
        )
        if getattr(settings, 'PARLIAMENT_ALERTS_BCC', ''):
            msg.bcc = [settings.PARLIAMENT_ALERTS_BCC]
        if rendered.get('html'):
            msg.attach_alternative(rendered['html'], 'text/html')
        if getattr(settings, 'PARLIAMENT_SEND_EMAIL', False):
            def _send(msg, retries):
                try:
                    msg.send()
                except SMTPException as e:
                    if retries > 0:
                        time.sleep(1)
                        _send(msg, retries=retries - 1)
                    else:
                        raise
            _send(msg, retries=2)
            self.last_sent = datetime.datetime.now()
            self.save()
        else:
            logger.error("settings.PARLIAMENT_SEND_EMAIL must be True to send mail")
            print(msg.subject)
            print(msg.body)
