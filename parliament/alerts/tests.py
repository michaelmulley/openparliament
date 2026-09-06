import datetime
import unittest
from unittest import mock

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings

from parliament.accounts.models import User
from parliament.alerts.matching import MatchingError, record_matches
from parliament.alerts.models import Subscription, Topic, TopicMatch
from parliament.alerts.templatetags.alerts import text_highlight
from parliament.search import es_index
from parliament.search.tests import DOCS, _es_available

TEST_ALIAS = 'parliament-alerts-test'
NOW = datetime.datetime(2026, 9, 5, 12)


def _msearch_response(*responses):
    return {'responses': list(responses)}


class MatchingErrorTests(TestCase):

    def setUp(self):
        user = User.objects.create(email='alerts@example.com')
        Subscription.objects.get_or_create_by_query('carbon tax', user)
        self.client_patch = mock.patch('parliament.alerts.matching.get_es_client')
        self.es = self.client_patch.start().return_value
        self.addCleanup(self.client_patch.stop)

    def test_retryable_error_fails_the_run(self):
        self.es.msearch.return_value = _msearch_response(
            {'error': {'type': 'search_phase_execution_exception', 'reason': 'shard failure'}, 'status': 503})
        with self.assertRaises(MatchingError):
            record_matches(['hansards.statement.1'], now=NOW)

    def test_query_error_is_logged_and_skipped(self):
        self.es.msearch.return_value = _msearch_response(
            {'error': {'type': 'parsing_exception', 'reason': 'bad query'}, 'status': 400})
        with self.assertLogs('parliament.alerts.matching', level='ERROR'):
            self.assertEqual(record_matches(['hansards.statement.1'], now=NOW), 0)


class TemplateTagTests(TestCase):

    def test_text_highlight(self):
        self.assertEqual(text_highlight('The <em>carbon</em> <em>tax</em> isn&#x27;t &quot;new&quot;.\n\nMore'),
                         'The **carbon** **tax** isn\'t "new". More')


@unittest.skipUnless(_es_available(), "Elasticsearch not reachable")
@override_settings(PARLIAMENT_ES_INDEX=TEST_ALIAS, PARLIAMENT_SEND_EMAIL=True,
                   SITE_URL='https://openparliament.ca')
class AlertMatchingTests(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.es = es_index.get_es_client()
        with override_settings(PARLIAMENT_ES_INDEX=TEST_ALIAS):
            for name in es_index.get_write_indices(cls.es):
                cls.es.indices.delete(index=name)
            index = es_index.create_index(es_index.new_index_name(), client=cls.es)
            es_index.index_documents(DOCS, index=index, client=cls.es)
            es_index.swap_alias(index, client=cls.es)

    @classmethod
    def tearDownClass(cls):
        for name in es_index.get_write_indices(cls.es):
            cls.es.indices.delete(index=name)
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create(email='alerts@example.com')

    def subscribe(self, query, user=None):
        sub, _ = Subscription.objects.get_or_create_by_query(query, user or self.user)
        return sub

    def test_topic_normalization(self):
        sub = self.subscribe('carbon tax Date: "2024-01 to 2025-01" Party: "Liberal"')
        self.assertEqual(sub.topic.query, 'carbon tax Party: "Liberal"')
        self.assertIn('sort=date+desc', sub.topic.get_search_url())

    def test_new_items_match_active_topics_only(self):
        sub = self.subscribe('carbon tax')
        paused = self.subscribe('rebate', User.objects.create(email='paused@example.com'))
        paused.active = False
        paused.save()

        found = record_matches(['hansards.statement.1', 'hansards.statement.2', 'bills.bill.10',
                                'core.politician.5'], now=NOW)
        self.assertEqual(found, 1)
        match = TopicMatch.objects.get()
        self.assertEqual((match.topic, match.item_id, match.url), (sub.topic, 'hansards.statement.1', '/debates/2026/8/1/a-1/'))
        self.assertEqual(match.created, NOW)
        self.assertEqual(match.date, datetime.datetime(2026, 8, 1, 14))
        self.assertIsNone(match.sent)
        self.assertEqual(Topic.objects.get(id=sub.topic_id).last_found, NOW)
        # Matching the same item again records nothing new
        self.assertEqual(record_matches(['hansards.statement.1'], now=NOW), 1)
        self.assertEqual(TopicMatch.objects.count(), 1)

    def test_reimported_statement_does_not_alert_again(self):
        self.subscribe('carbon tax')
        record_matches(['hansards.statement.1'], now=NOW)
        # A re-import replaces the statement: new primary key, same URL
        reimported = dict(DOCS[0], id='hansards.statement.1001', django_id='1001')
        es_index.index_documents([reimported], client=self.es)
        try:
            record_matches(['hansards.statement.1001'], now=NOW)
            match = TopicMatch.objects.get()
            self.assertEqual((match.url, match.item_id), ('/debates/2026/8/1/a-1/', 'hansards.statement.1001'))
            # ...and the e-mail finds the statement under its new identifier
            call_command('send_email_alerts')
            self.assertEqual(len(mail.outbox), 1)
            self.assertIn('/debates/2026/8/1/a-1/', mail.outbox[0].body)
            # Re-importing an already-sent item doesn't resurrect it
            record_matches(['hansards.statement.1001'], now=NOW)
            self.assertIsNotNone(TopicMatch.objects.get().sent)
        finally:
            es_index.delete_documents(['hansards.statement.1001'], client=self.es)

    def test_slug_change_on_reimport_does_not_alert_again(self):
        from parliament.core.models import Session
        from parliament.hansards.models import Document, OldSlugMapping, Statement
        session = Session.objects.create(id='45-1', name='45th Parliament, 1st Session', start=datetime.date(2025, 4, 29))
        doc = Document.objects.create(document_type='D', date=datetime.date(2026, 8, 1), session=session, source_id=1)
        statement = dict(document=doc, time=datetime.datetime(2026, 8, 1, 14), content_en='<p>The carbon tax rebate.</p>',
                         sequence=1, wordcount=40, wordcount_en=40)
        Statement.objects.create(id=1, slug='a-1', urlcache='/debates/2026/8/1/a-1/', **statement)
        self.subscribe('carbon tax')
        record_matches(['hansards.statement.1'], now=NOW)
        self.assertEqual(TopicMatch.objects.get().url, '/debates/2026/8/1/a-1/')

        # A re-import that changes the slug: new primary key, new URL, and a mapping
        Statement.objects.get(id=1).delete()
        Statement.objects.create(id=1002, slug='a-a-1', urlcache='/debates/2026/8/1/a-a-1/', **statement)
        OldSlugMapping.objects.create(document=doc, old_slug='a-1', new_slug='a-a-1')
        es_index.index_documents([dict(DOCS[0], id='hansards.statement.1002', django_id='1002',
                                       url='/debates/2026/8/1/a-a-1/')], client=self.es)
        try:
            self.assertEqual(record_matches(['hansards.statement.1002'], now=NOW), 0)
            match = TopicMatch.objects.get()
            self.assertEqual((match.url, match.item_id), ('/debates/2026/8/1/a-a-1/', 'hansards.statement.1002'))
            call_command('send_email_alerts')
            self.assertEqual(len(mail.outbox), 1)
            self.assertIn('/debates/2026/8/1/a-a-1/', mail.outbox[0].body)
        finally:
            es_index.delete_documents(['hansards.statement.1002'], client=self.es)

    def test_old_items_do_not_alert(self):
        self.subscribe('rebate')
        # Statement 2 (2016) matches "rebate" but is far older than the window
        record_matches(['hansards.statement.2'], now=NOW)
        self.assertEqual(TopicMatch.objects.count(), 0)
        record_matches(['hansards.statement.2'], now=datetime.datetime(2016, 8, 15))
        self.assertEqual(TopicMatch.objects.count(), 1)

    def test_every_term_required(self):
        self.subscribe('carbon zebra')
        record_matches(['hansards.statement.1'], now=NOW)
        self.assertEqual(TopicMatch.objects.count(), 0)

    def test_send_email_alerts(self):
        sub = self.subscribe('carbon tax')
        record_matches(['hansards.statement.1'], now=NOW)

        call_command('send_email_alerts')
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ['alerts@example.com'])
        self.assertIn('carbon tax', message.subject)
        self.assertIn('https://openparliament.ca/debates/2026/8/1/a-1/', message.body)
        self.assertIn('**carbon** **tax**', message.body)
        self.assertIn('August 1st', message.body)
        self.assertNotIn('more. See them all', message.body)
        self.assertIn(sub.get_unsubscribe_url(), message.body)
        self.assertIsNotNone(TopicMatch.objects.get().sent)
        self.assertIsNotNone(Subscription.objects.get(id=sub.id).last_sent)

        # Nothing new: nothing sent
        call_command('send_email_alerts')
        self.assertEqual(len(mail.outbox), 1)

    def test_more_than_fit_in_one_email(self):
        self.subscribe('zebra')
        es_index.index_documents([{
            'id': f'hansards.statement.{n}', 'django_ct': 'hansards.statement', 'django_id': str(n),
            'doctype': 'debate', 'date': f'2026-09-0{n}T14:00:00Z', 'url': f'/debates/2026/9/{n}/z-1/',
            'politician': 'Zed Zebra', 'text_en': f'Zebra statement number {n}.', 'procedural': False, 'wordcount': 40,
        } for n in (1, 2, 3)], client=self.es)
        try:
            record_matches(['hansards.statement.1', 'hansards.statement.2', 'hansards.statement.3'], now=NOW)
            self.assertEqual(TopicMatch.objects.count(), 3)
            with mock.patch('parliament.alerts.management.commands.send_email_alerts.ALERT_MAX_ITEMS', 2):
                call_command('send_email_alerts')
            body = mail.outbox[0].body
            self.assertIn('/debates/2026/9/3/z-1/', body)  # newest first
            self.assertIn('/debates/2026/9/2/z-1/', body)
            self.assertNotIn('/debates/2026/9/1/z-1/', body)
            self.assertIn('...and 1 more.', body)
            self.assertIn('https://openparliament.ca/search/?q=zebra&sort=date+desc', body)
            self.assertEqual(TopicMatch.objects.filter(sent__isnull=True).count(), 0)
        finally:
            es_index.delete_documents(['hansards.statement.1', 'hansards.statement.2', 'hansards.statement.3'], client=self.es)
            es_index.index_documents([d for d in DOCS if d['id'] in ('hansards.statement.1', 'hansards.statement.2', 'hansards.statement.3')], client=self.es)

    def test_mp_hansard_alert(self):
        sub = self.subscribe('MP: "amelie-belanger" Type: "debate"')
        self.assertTrue(sub.topic.politician_hansard_alert)
        record_matches(['hansards.statement.1', 'hansards.statement.3', 'hansards.statement.4'], now=NOW)
        self.assertEqual([m.item_id for m in TopicMatch.objects.all()], ['hansards.statement.1'])
        with mock.patch('parliament.core.models.PoliticianManager.get_by_slug_or_id') as get_by_slug:
            get_by_slug.return_value = mock.Mock(name='Amélie Bélanger')
            call_command('send_email_alerts')
        body = mail.outbox[0].body
        self.assertIn("what Amélie Bélanger had to say in the House", body)
        # Full text, not a snippet, and no highlighting markup
        self.assertIn('The carbon tax rebate is a <b>good</b> thing', body)
        self.assertNotIn('**carbon**', body)

    def test_bouncing_addresses_are_skipped_but_matches_still_cleared(self):
        self.subscribe('carbon tax')
        self.user.email_bouncing = True
        self.user.save()
        record_matches(['hansards.statement.1'], now=NOW)
        call_command('send_email_alerts')
        self.assertEqual(len(mail.outbox), 0)
        self.assertIsNotNone(TopicMatch.objects.get().sent)
