import datetime
import unittest
from unittest import mock

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils.safestring import mark_safe

from parliament.accounts.models import User
from parliament.alerts.matching import MatchingError, record_matches
from parliament.alerts import models as alert_models
from parliament.alerts.models import Subscription, Topic, TopicMatch
from parliament.alerts.templatetags.alerts import email_paragraphs, html_highlight, text_highlight
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

    def test_html_highlight(self):
        self.assertEqual(html_highlight('The <em>carbon</em> tax isn&#x27;t &lt;new&gt;.\n\nMore'),
                         'The <strong style="%s">carbon</strong> tax isn&#x27;t &lt;new&gt;. More'
                         % 'background-color:#fff3b0;color:#222222;font-weight:bold;')

    def test_email_paragraphs(self):
        self.assertEqual(email_paragraphs('Taxes & <b>rebates</b>.\nYes.\n\n\nSecond.'),
                         '<p style="margin:0 0 12px 0;">Taxes &amp; &lt;b&gt;rebates&lt;/b&gt;.<br>Yes.</p>'
                         '<p style="margin:0 0 12px 0;">Second.</p>')


@override_settings(SITE_URL='https://openparliament.ca')
class HTMLEmailTests(TestCase):
    """Rendering alert e-mails from search documents, without Elasticsearch."""

    def subscription(self, query):
        sub, _ = Subscription.objects.get_or_create_by_query(
            query, User.objects.create(email='alerts@example.com'))
        return sub

    def found(self, doc):
        """A search document as SearchQuery returns it: snippets default to its text."""
        doc.setdefault('snippets', [doc['text']] if doc.get('text') else [])
        return doc

    def statement(self, n, **kwargs):
        return self.found(dict({'django_ct': 'hansards.statement', 'date': NOW - datetime.timedelta(hours=n),
                                'url': f'/debates/2026/9/5/s-{n}/', 'politician': 'Amélie Bélanger',
                                'topic': f'Topic {n}'}, **kwargs))

    def test_search_alert(self):
        sub = self.subscription('carbon tax')
        documents = [
            self.statement(1, text=mark_safe('The <em>carbon</em> <em>tax</em> &amp; &lt;rebate&gt;')),
            self.found({'django_ct': 'bills.bill', 'date': NOW, 'url': '/bills/45-1/C-11/', 'number': 'C-11',
                        'title': 'Carbon Tax Act', 'text': mark_safe('A <em>carbon</em> <em>tax</em>.')}),
            # Statements without a politician, with and without a committee
            self.statement(2, politician='', topic='', committee='Finance', text='A carbon tax.'),
            {k: v for k, v in self.statement(3, text='A carbon tax.').items() if k not in ('politician', 'topic')},
            # Two passages shown, and more matches than that
            self.statement(4, text=mark_safe('First <em>carbon</em> tax.'), more_snippets=True,
                           snippets=[mark_safe('First <em>carbon</em> tax.'), mark_safe('Second <em>carbon</em> tax.')]),
        ]
        html = sub.render_message(documents, more=3)['html']
        self.assertIn('<!doctype html>', html)
        self.assertIn('https://openparliament.ca/debates/2026/9/5/s-1/', html)
        self.assertIn('Amélie Bélanger on Topic 1', html)
        self.assertIn('<strong style="background-color:#fff3b0;color:#222222;font-weight:bold;">carbon</strong>', html)
        self.assertIn('&amp; &lt;rebate&gt;', html)
        self.assertIn('Bill C-11', html)
        self.assertIn('>Finance committee</a>', html)
        self.assertIn('>In Parliament</a>', html)
        self.assertIn('>… Second <strong', html)
        self.assertEqual(html.count('More mentions in the full text'), 1)
        self.assertIn('<a href="https://openparliament.ca/debates/2026/9/5/s-4/" style="color:#1A59C7;">More mentions', html)
        self.assertIn('…and 3 more.', html)
        self.assertIn('https://openparliament.ca/search/?q=carbon+tax&amp;sort=date+desc', html)
        self.assertIn(sub.get_unsubscribe_url(full=True), html)
        # The preview text is the first snippet, unescaped and then escaped once
        self.assertIn('The carbon tax &amp; &lt;rebate&gt;</div>', html)

    def test_mp_alert_keeps_html_under_gmail_clipping_size(self):
        sub = self.subscription('MP: "amelie-belanger" Type: "debate"')
        speech = 'Mr. Speaker, the carbon tax rebate is a good thing for taxpayers & families.\n\n' * 400
        documents = [self.statement(n, text='', full_text=speech) for n in range(25)]
        rendered = sub.render_message(documents)
        self.assertGreater(len(rendered['text']), 25 * len(speech))  # the plain text has it all
        html = rendered['html']
        self.assertLess(len(html.encode('utf-8')), 100 * 1024)
        self.assertIn("Here's what <strong>Amélie Bélanger</strong> had to say", html)
        self.assertIn('Continue reading on openparliament.ca', html)
        self.assertIn('Read it on openparliament.ca', html)
        self.assertIn('https://openparliament.ca/debates/2026/9/5/s-24/', html)

    def test_full_text_budget(self):
        documents = [{'full_text': 'a b c d e'}, {'full_text': 'x' * 500}, {'full_text': 'f g h ' * 200},
                     {'full_text': 'tiny'}]
        result = alert_models._budget_full_text(documents, budget=1000)
        self.assertEqual([d['email_text_truncated'] for d in result], [False, False, True, True])
        self.assertEqual(result[0]['email_text'], 'a b c d e')
        self.assertRegex(result[2]['email_text'], r'^([fgh] )+[fgh]…$')
        self.assertEqual(result[3]['email_text'], '')
        self.assertLessEqual(sum(len(d['email_text']) for d in result), 1000)
        # Once the remaining budget is below the minimum excerpt, text is left out entirely
        result = alert_models._budget_full_text(documents, budget=600)
        self.assertEqual(result[2]['email_text'], '')
        self.assertTrue(result[2]['email_text_truncated'])

    def test_compile_failure_stops_the_send(self):
        sub = self.subscription('carbon tax')
        with mock.patch('parliament.alerts.models.mrml.to_html', side_effect=OSError('bad mjml')), \
                override_settings(PARLIAMENT_SEND_EMAIL=True), self.assertRaises(OSError):
            sub.send_email([self.statement(1, text=mark_safe('<em>carbon</em> tax'))])
        self.assertEqual(len(mail.outbox), 0)


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
        html, mimetype = message.alternatives[0]
        self.assertEqual(mimetype, 'text/html')
        self.assertIn('https://openparliament.ca/debates/2026/8/1/a-1/', html)
        self.assertIn('>carbon</strong> <strong', html)

        # Nothing new: nothing sent
        call_command('send_email_alerts')
        self.assertEqual(len(mail.outbox), 1)

    def test_two_snippets_and_more_mentions(self):
        self.subscribe('zebra')
        filler = 'Nothing in particular happened at the farm today. ' * 8
        mentions = ['A zebra escaped.', 'The zebra was found.', 'Zebra fences are planned.']
        es_index.index_documents([{
            'id': f'hansards.statement.{n}', 'django_ct': 'hansards.statement', 'django_id': str(n),
            'doctype': 'debate', 'date': f'2026-09-0{n - 19}T14:00:00Z', 'url': f'/debates/2026/9/{n - 19}/z-1/',
            'politician': 'Zed Zebra', 'procedural': False, 'wordcount': 200,
            'text_en': filler.join(mentions[:count]),
        } for n, count in ((20, 3), (21, 2))], client=self.es)
        try:
            record_matches(['hansards.statement.20', 'hansards.statement.21'], now=NOW)
            call_command('send_email_alerts')
            message = mail.outbox[0]
            # Three mentions: two shown, and a pointer to the rest
            # Newest first: the two-mention statement (Sept. 2), then the three-mention one (Sept. 1)
            two, three = message.body.split('/debates/2026/9/1/z-1/')
            self.assertEqual(three.count('**zebra**') + three.count('**Zebra**'), 2)
            self.assertIn('More mentions in the full text', three)
            # Two mentions: both shown, nothing more
            self.assertEqual(two.count('**zebra**') + two.count('**Zebra**'), 2)
            self.assertNotIn('More mentions', two)
            html = message.alternatives[0][0]
            self.assertEqual(html.count('More mentions in the full text'), 1)
        finally:
            es_index.delete_documents(['hansards.statement.20', 'hansards.statement.21'], client=self.es)

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
        html = mail.outbox[0].alternatives[0][0]
        self.assertIn('The carbon tax rebate is a &lt;b&gt;good&lt;/b&gt; thing', html)

    def test_bouncing_addresses_are_skipped_but_matches_still_cleared(self):
        self.subscribe('carbon tax')
        self.user.email_bouncing = True
        self.user.save()
        record_matches(['hansards.statement.1'], now=NOW)
        call_command('send_email_alerts')
        self.assertEqual(len(mail.outbox), 0)
        self.assertIsNotNone(TopicMatch.objects.get().sent)
