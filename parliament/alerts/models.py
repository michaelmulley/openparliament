import base64
import datetime
import hashlib
import html
import re
from smtplib import SMTPException
import time

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.signing import Signer
from django.urls import reverse
from urllib.parse import urlencode
from django.db import models
from django.template import loader
from django.utils.html import strip_tags
import mrml

from parliament.core.models import Politician
from parliament.core.templatetags.ours import english_list
from parliament.core.utils import ActiveManager
from parliament.search.es import SearchQuery

import logging
logger = logging.getLogger(__name__)

# Highlighted passages shown per item in a search alert
ALERT_SNIPPETS = 2

# Gmail clips messages over about 102KB of HTML, hiding the footer and its
# unsubscribe link. MP alerts carry whole speeches, so their HTML includes at
# most this many characters of speech; the rest is a link away.
HTML_EMAIL_TEXT_BUDGET = 40000


def _budget_full_text(documents, budget=HTML_EMAIL_TEXT_BUDGET):
    """Copies of search documents, each with an `email_text`: its full
    text, cut short at a word boundary once `budget` characters have been
    used (`email_text_truncated` is then set)."""
    result = []
    for doc in documents:
        text = doc.get('full_text', '')
        truncated = len(text) > budget
        if truncated:
            # No excerpt at all beats a uselessly short one
            text = text[:budget].rsplit(None, 1)[0] + '…' if budget >= 300 else ''
        budget -= len(text)
        result.append(dict(doc, email_text=text, email_text_truncated=truncated))
    return result


def render_mjml(template_name, ctx):
    """Renders a Django template of MJML and compiles it to e-mail HTML."""
    output = mrml.to_html(loader.render_to_string(template_name, ctx))
    for warning in output.warnings:
        logger.warning("MJML warning in %s: %s", template_name, warning)
    return output.content


class TopicManager(models.Manager):

    def get_or_create_by_query(self, query):
        query_obj = SearchQuery(query)
        if 'Date' in query_obj.filters:
            del query_obj.filters['Date']  # Date filters make no sense in alerts
        normalized_query = query_obj.normalized_query
        if not normalized_query:
            raise ValueError("Invalid query")
        return self.get_or_create(query=normalized_query)

    def active(self):
        """Topics somebody is currently subscribed to."""
        return self.filter(subscription__active=True).distinct()


class Topic(models.Model):
    """A search that one or more people have saved.

    Statements and bills are matched against every active topic as they are
    indexed (parliament.alerts.matching records a TopicMatch for each hit),
    and send_email_alerts mails out the matches recorded since its last run.
    """
    query = models.CharField(max_length=800, unique=True)
    created = models.DateTimeField(default=datetime.datetime.now)
    last_checked = models.DateTimeField(blank=True, null=True)  # last time alerts were sent for it
    last_found = models.DateTimeField(blank=True, null=True)  # last time a new item matched it

    objects = TopicManager()

    def __str__(self):
        if self.politician_hansard_alert:
            return '%s in House debates' % self.person_name
        return self.query

    def search_query(self, ids, full_text=False):
        """The topic's search, restricted to the given search identifiers
        (e.g. hansards.statement.123), newest first, every term required."""
        return SearchQuery(self.query, limit=len(ids), user_params={'sort': 'date desc'},
                           full_text=full_text, minimum_should_match='100%', ids=list(ids),
                           snippets=ALERT_SNIPPETS)

    def get_documents(self, matches):
        """Search-result documents for TopicMatch objects, newest first, with
        the highlighted snippets the alert e-mails show."""
        if not matches:
            return []
        documents = self.search_query([m.item_id for m in matches],
                                      full_text=self.politician_hansard_alert).documents
        if self.politician_hansard_alert:
            # Leave out the procedural odds and ends
            documents = [d for d in documents if not d.get('procedural')]
        return documents

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

    def get_search_url(self, full=True):
        return (settings.SITE_URL if full else '') + reverse('search') + '?' + urlencode(
            {'q': self.query, 'sort': 'date desc'})


class TopicMatch(models.Model):
    """A newly indexed item that matched a topic: waiting to be e-mailed, or
    (once `sent` is set) already sent.

    Keyed on the item's URL, not its search identifier: re-importing a
    Hansard document replaces its statements (new primary keys) but keeps
    their slugs, and a re-import isn't news. When a re-import does change
    slugs, matching follows OldSlugMapping to carry the record forward."""
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='matches')
    url = models.CharField(max_length=400)
    item_id = models.CharField(max_length=100)  # current search identifier, e.g. hansards.statement.123
    date = models.DateTimeField()  # the item's own date
    created = models.DateTimeField(default=datetime.datetime.now)
    sent = models.DateTimeField(blank=True, null=True, db_index=True)

    class Meta:
        unique_together = [
            ('topic', 'url')
        ]

    def __str__(self):
        return '%s matched %s' % (self.item_id, self.topic)


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

    def get_unsubscribe_url(self, full=False):
        key = Signer(salt='alerts_unsubscribe').sign(str(self.id))
        return (settings.SITE_URL if full else '') + reverse(
            'alerts_unsubscribe', kwargs={'key': key})

    def render_message(self, documents, more=0):
        ctx = {
            'documents': documents,
            'more': more,  # matches beyond those shown
            'search_url': self.topic.get_search_url(),
            'unsubscribe_url': self.get_unsubscribe_url(full=True),
            'site_url': settings.SITE_URL,
            'subject': self.get_subject_line(documents),
        }

        if self.topic.politician_hansard_alert:
            ctx['person_name'] = documents[0]['politician']
            text = loader.render_to_string('alerts/mp_hansard_alert.txt', ctx)
            ctx.update(documents=_budget_full_text(documents),
                       preview=documents[0].get('full_text', ''))
            return dict(text=text, html=render_mjml('alerts/mp_hansard_alert.mjml', ctx))

        ctx.update(
            topic=self.topic,
            preview=html.unescape(strip_tags(documents[0]['text'])),
        )
        text = loader.render_to_string('alerts/search_alert.txt', ctx)
        return dict(text=text, html=render_mjml('alerts/search_alert.mjml', ctx))

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

    def send_email(self, documents, more=0):
        rendered = self.render_message(documents, more=more)
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
