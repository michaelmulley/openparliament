import datetime
import unittest
from unittest import mock

from django.test import SimpleTestCase, override_settings

from parliament.search import es_index
from parliament.search.es import (
    MINIMUM_SHOULD_MATCH, SearchQuery, apply_suggestions, build_search_body,
    build_suggest_body, find_bill_numbers, normalize_query, split_negations)
from parliament.search.management.commands.consume_indexing_queue import collapse_tasks
from parliament.search.models import IndexingTask
from parliament.search.utils import parse_date_filter, politician_result_html, title_key

NOW = datetime.datetime(2026, 9, 5, 12)


def sqs(body):
    """The simple_query_string clause of a body."""
    q = body['query']
    if 'function_score' in q:
        q = q['function_score']['query']
    return q['bool']['must'][0]['simple_query_string']


def functions(body):
    return body['query']['function_score']['functions']


class QueryParsingTests(SimpleTestCase):

    def test_filters_are_extracted_from_query(self):
        q = SearchQuery('carbon tax Party: "Conservative" Date: "2024-03"')
        self.assertEqual(q.bare_query, 'carbon tax')
        self.assertEqual(q.filters, {'Party': 'Conservative', 'Date': '2024-03'})
        self.assertEqual(q.normalized_query, 'carbon tax Date: "2024-03" Party: "Conservative"')

    def test_unknown_filter_stays_in_query(self):
        q = SearchQuery('Foo: "bar" baz')
        self.assertEqual(q.bare_query, 'Foo: "bar" baz')
        self.assertEqual(q.filters, {})

    def test_date_filter_parsing(self):
        d = datetime.date
        self.assertEqual(parse_date_filter('2024-03'), (d(2024, 3, 1), d(2024, 4, 1)))
        self.assertEqual(parse_date_filter('2024-03-05'), (d(2024, 3, 5), d(2024, 3, 6)))
        self.assertEqual(parse_date_filter('2023-01 to 2024-02'), (d(2023, 1, 1), d(2024, 3, 1)))
        self.assertEqual(parse_date_filter('2023-01-15 to 2024-02-10'), (d(2023, 1, 15), d(2024, 2, 11)))
        self.assertIsNone(parse_date_filter('last week'))
        self.assertIsNone(parse_date_filter('2024-13'))

    def test_bill_numbers(self):
        self.assertEqual(find_bill_numbers('c-11'), ['c-11'])
        self.assertEqual(find_bill_numbers('Bill C-11 and S-5'), ['c-11', 's-5'])
        self.assertEqual(find_bill_numbers('C11'), ['c-11'])
        self.assertEqual(find_bill_numbers('c-11-2'), [])
        self.assertEqual(find_bill_numbers('covid-19'), [])
        self.assertEqual(find_bill_numbers('carbon tax'), [])

    def test_normalize_query(self):
        self.assertEqual(normalize_query('“carbon tax” rebate'), ('"carbon tax" rebate', False))
        self.assertEqual(normalize_query('Ukraine AND reconstruction'), ('Ukraine reconstruction', True))
        self.assertEqual(normalize_query('climate OR environment OR kyoto'), ('climate | environment | kyoto', True))
        self.assertEqual(normalize_query('housing NOT affordability'), ('housing -affordability', True))
        self.assertEqual(normalize_query('"security screening" & Wex'), ('"security screening" Wex', True))
        # Lowercase and/or are ordinary words
        self.assertEqual(normalize_query('war and peace'), ('war and peace', False))
        self.assertEqual(normalize_query('a | b'), ('a | b', True))

    def test_split_negations(self):
        self.assertEqual(split_negations('rebate -carbon'), ('rebate', ['carbon']))
        self.assertEqual(split_negations('-carbon rebate -"tax credit"'), ('rebate', ['carbon', '"tax credit"']))
        self.assertEqual(split_negations('covid-19 C-11 x-y'), ('covid-19 C-11 x-y', []))
        self.assertEqual(split_negations('-carbon'), ('', ['carbon']))

    def test_title_key(self):
        self.assertEqual(title_key("Companies' Creditors Arrangement Act"), 'companies creditors arrangement act')
        self.assertEqual(title_key('Loi sur la diffusion continue en ligne'), 'loi sur la diffusion continue en ligne')
        self.assertEqual(title_key('  Online   Streaming Act. '), 'online streaming act')
        self.assertEqual(title_key('Rosemont—La Petite-Patrie'), 'rosemont la petite patrie')
        self.assertEqual(title_key('Desnethé—Missinippi—Churchill River'), 'desnethe missinippi churchill river')
        self.assertIsNone(title_key('...'))
        self.assertIsNone(title_key(''))

    def test_politician_result_html(self):
        self.assertEqual(
            politician_result_html('Liberal', 'Lib', 'Papineau', None),
            '<span class="tag partytag_lib">Liberal</span> MP for Papineau')
        self.assertEqual(
            politician_result_html('NDP', 'NDP', 'Burnaby South', 2025),
            'was <span class="tag partytag_ndp">NDP</span> MP for Burnaby South until 2025')

    def test_apply_suggestions(self):
        response = {'suggest': {'terms': [
            {'text': 'defence', 'offset': 0, 'length': 7, 'options': []},
            {'text': 'procurment', 'offset': 8, 'length': 10, 'options': [{'text': 'procurement', 'freq': 900}]},
        ]}}
        self.assertEqual(apply_suggestions('defence procurment', response), 'defence procurement')
        self.assertEqual(apply_suggestions('Anthony Housfather', {'suggest': {'terms': [
            {'text': 'housfather', 'offset': 8, 'length': 10, 'options': [{'text': 'housefather'}]}]}}),
            'Anthony Housefather')
        self.assertIsNone(apply_suggestions('fine', {'suggest': {'terms': [{'text': 'fine', 'offset': 0, 'length': 4, 'options': []}]}}))
        self.assertEqual(build_suggest_body('nucledar')['suggest']['terms']['term']['suggest_mode'], 'missing')


class QueryBuilderTests(SimpleTestCase):

    def test_text_query(self):
        body = build_search_body('carbon tax', {}, now=NOW)
        clause = sqs(body)
        self.assertEqual(clause['query'], 'carbon tax')
        self.assertEqual(clause['quote_field_suffix'], '.exact')
        self.assertEqual(clause['default_operator'], 'or')
        self.assertEqual(clause['minimum_should_match'], MINIMUM_SHOULD_MATCH)
        self.assertIn('text_en', clause['fields'])
        self.assertIn('bill_text_en', clause['fields'])
        self.assertIn('boosted^3', clause['fields'])
        # Relevance multiplied by recency and the discounts
        fs = body['query']['function_score']
        self.assertEqual(fs['boost_mode'], 'multiply')
        self.assertEqual(fs['score_mode'], 'multiply')
        self.assertIn('script_score', fs['functions'][0])
        self.assertEqual(fs['functions'][1]['filter'], {'term': {'procedural': True}})
        self.assertEqual(fs['functions'][2]['filter'], {'range': {'wordcount': {'lt': 30}}})
        # Former MPs decay from the year they left
        self.assertIn("doc['end_year']", fs['functions'][0]['script_score']['script']['source'])
        # An exact bill title, MP name or riding multiplies too
        self.assertEqual(fs['functions'][3], {'filter': {'term': {'title_key': 'carbon tax'}}, 'weight': 10.0})
        self.assertEqual(body['highlight']['highlight_query'], {'bool': {'must': fs['query']['bool']['must']}})
        self.assertNotIn('sort', body)
        self.assertEqual(set(body['highlight']['fields']), {'text_en', 'bill_text_en'})
        self.assertEqual(body['highlight']['fields']['text_en'], {'matched_fields': ['text_en', 'text_en.exact']})
        self.assertEqual(body['_source'], {'excludes': ['text_*', 'bill_text_*']})
        # Just the best passage...
        self.assertEqual(body['highlight']['number_of_fragments'], 1)
        self.assertNotIn('order', body['highlight'])
        # ...or several, best first, plus one to tell whether there are other matches
        highlight = build_search_body('carbon tax', {}, now=NOW, snippets=2)['highlight']
        self.assertEqual((highlight['number_of_fragments'], highlight['order']), (3, 'score'))

    def test_phrase_boosts_only_for_multiple_terms(self):
        should = build_search_body('carbon tax', {}, now=NOW)['query']['function_score']['query']['bool']['should']
        self.assertEqual([(c['multi_match']['slop'], c['multi_match']['boost']) for c in should], [(2, 2.0), (40, 1.0)])
        self.assertEqual(should[0]['multi_match']['query'], 'carbon tax')
        bool_q = build_search_body('carbon', {}, now=NOW)['query']['function_score']['query']['bool']
        self.assertNotIn('should', bool_q)

    def test_phrase_boost_strips_syntax(self):
        should = build_search_body('"carbon tax" +rebate', {}, now=NOW)['query']['function_score']['query']['bool']['should']
        self.assertEqual(should[0]['multi_match']['query'], 'carbon tax rebate')

    def test_explicit_operators(self):
        body = build_search_body('Ukraine AND reconstruction', {}, now=NOW)
        clause = sqs(body)
        self.assertEqual(clause['query'], 'Ukraine reconstruction')
        self.assertEqual(clause['default_operator'], 'and')
        self.assertNotIn('minimum_should_match', clause)
        # No phrase or title bonuses for boolean queries
        self.assertNotIn('should', body['query']['function_score']['query']['bool'])
        self.assertEqual(len(functions(body)), 3)
        self.assertEqual(sqs(build_search_body('a OR b OR c', {}, now=NOW))['query'], 'a | b | c')

    def test_curly_quotes(self):
        self.assertEqual(sqs(build_search_body('“carbon tax”', {}, now=NOW))['query'], '"carbon tax"')

    def test_negations_become_must_not(self):
        bool_q = build_search_body('rebate -carbon -"tax credit"', {}, now=NOW)['query']['function_score']['query']['bool']
        self.assertEqual(bool_q['must'][0]['simple_query_string']['query'], 'rebate')
        self.assertEqual(bool_q['must_not'][0]['multi_match']['query'], 'carbon')
        self.assertEqual(bool_q['must_not'][1]['multi_match']['type'], 'phrase')
        self.assertIn('text_en.exact', bool_q['must_not'][1]['multi_match']['fields'])
        # Only exclusions: no scoring, newest first
        body = build_search_body('-carbon', {}, now=NOW)
        self.assertEqual(list(body['query']['bool']), ['must_not'])
        self.assertEqual(body['sort'][0]['date']['order'], 'desc')

    def test_bill_number_query(self):
        for q in ('C-11', 'bill c-11', 'c11'):
            fs = build_search_body(q, {}, now=NOW)['query']['function_score']
            # Text relevance replaced by: is it the bill, then recency
            self.assertEqual(fs['boost_mode'], 'replace')
            self.assertEqual(fs['functions'][0], {'filter': {'terms': {'number': ['c-11']}}, 'weight': 1e6})
            self.assertIn('script_score', fs['functions'][1])
        fs = build_search_body('C-11 streaming', {}, now=NOW)['query']['function_score']
        self.assertEqual(fs['boost_mode'], 'multiply')
        self.assertEqual(fs['query']['bool']['should'][-1], {'terms': {'number': ['c-11'], 'boost': 50}})

    def test_filters_only(self):
        body = build_search_body('', {'politician_id': 'justin-trudeau', 'doctype': 'debate'}, now=NOW)
        self.assertEqual(body['query'], {'bool': {'filter': [
            {'term': {'politician_id': 'justin-trudeau'}}, {'term': {'doctype': 'debate'}}]}})
        # Nothing to rank by, so newest first
        self.assertEqual(body['sort'], [{'date': {'order': 'desc', 'missing': '_last'}}])

    def test_sort_by_date_skips_scoring(self):
        body = build_search_body('carbon tax', {}, sort='date asc', now=NOW)
        self.assertIn('bool', body['query'])
        self.assertEqual(body['sort'], [{'date': {'order': 'asc', 'missing': '_last'}}])

    def test_facets_use_post_filter_and_exclusions(self):
        body = build_search_body('tax', {'party': 'Liberal', 'committee_slug': 'finance', 'date': '2024-01'},
                                 facet=True, now=NOW)
        bool_q = body['query']['function_score']['query']['bool']
        # committee filter isn't excluded by any facet, so it narrows the query
        self.assertEqual(bool_q['filter'], [{'term': {'committee_slug': 'finance'}}])
        self.assertEqual(body['post_filter']['bool']['filter'], [
            {'term': {'party': 'Liberal'}},
            {'range': {'date': {'gte': '2024-01-01', 'lt': '2024-02-01'}}},
        ])
        aggs = body['aggs']
        # The party facet ignores the party filter but respects the date one
        self.assertEqual(aggs['party']['filter']['bool']['filter'],
                         [{'range': {'date': {'gte': '2024-01-01', 'lt': '2024-02-01'}}}])
        # The province facet respects both
        self.assertEqual(len(aggs['province']['filter']['bool']['filter']), 2)
        # The date histogram ignores the date filter
        self.assertEqual(aggs['date']['filter']['bool']['filter'], [{'term': {'party': 'Liberal'}}])
        histogram = aggs['date']['aggs']['values']['date_histogram']
        self.assertEqual(histogram['extended_bounds'], {'min': '1994', 'max': '2026'})
        self.assertEqual(histogram['hard_bounds'], {'min': '1994', 'max': '2027'})

    def test_no_facets_means_all_filters_in_query(self):
        body = build_search_body('tax', {'party': 'Liberal'}, facet=False, now=NOW)
        self.assertNotIn('post_filter', body)
        self.assertNotIn('aggs', body)
        self.assertEqual(body['query']['function_score']['query']['bool']['filter'],
                         [{'term': {'party': 'Liberal'}}])

    def test_ids_restrict_the_search(self):
        body = build_search_body('tax', {}, ids=['hansards.statement.1', 'bills.bill.2'], now=NOW)
        self.assertIn({'ids': {'values': ['hansards.statement.1', 'bills.bill.2']}},
                      body['query']['function_score']['query']['bool']['filter'])

    def test_witness_filter_must_be_numeric(self):
        body = build_search_body('', {'who_hocid': '12345'}, now=NOW)
        self.assertEqual(body['query']['bool']['filter'], [{'term': {'who_hocid': 12345}}])
        body = build_search_body('', {'who_hocid': 'nope'}, now=NOW)
        self.assertEqual(body['query'], {'match_all': {}})

    def test_search_query_maps_user_filters(self):
        q = SearchQuery('tax Party: "Liberal" Type: "committee" Committee: "finance"',
                        user_params={'sort': 'date desc'}, facet=True)
        body = q.get_search_body()
        self.assertTrue(q.committees_only)
        self.assertEqual(body['aggs']['date']['aggs']['values']['date_histogram']['extended_bounds']['min'], '2006')
        self.assertEqual(body['sort'][0]['date']['order'], 'desc')

    def test_invalid_sort_ignored(self):
        q = SearchQuery('tax', user_params={'sort': 'evil'})
        self.assertEqual(q.validated_user_params, {})

    def test_full_text_and_minimum_should_match(self):
        q = SearchQuery('tax', full_text=True, minimum_should_match='100%')
        body = q.get_search_body()
        self.assertNotIn('_source', body)
        self.assertEqual(sqs(body)['minimum_should_match'], '100%')

    def test_suggestion_count_applies_the_users_filters(self):
        q = SearchQuery('carbn tax Party: "Conservative"', facet=True)
        # Search: no results; suggester: a correction; count: enough results
        client = mock.Mock()
        client.search.side_effect = [
            {'hits': {'total': {'value': 0}, 'hits': []}, 'aggregations': {}},
            {'suggest': {'terms': [{'text': 'carbn', 'offset': 0, 'length': 5,
                                    'options': [{'text': 'carbon'}]},
                                   {'text': 'tax', 'offset': 6, 'length': 3, 'options': []}]}},
        ]
        client.count.return_value = {'count': 12}
        with mock.patch('parliament.search.es.get_es_client', return_value=client):
            self.assertEqual(q.suggestion, 'carbon tax Party: "Conservative"')
        counted = client.count.call_args.kwargs['query']
        # Facets put the party filter in a post_filter; the count must apply it
        self.assertIn({'term': {'party': 'Conservative'}}, counted['function_score']['query']['bool']['filter'])
        self.assertEqual(sqs({'query': counted})['query'], 'carbon tax')

    def test_french(self):
        body = build_search_body('taxe', {}, language='fr', now=NOW)
        self.assertIn('text_fr', sqs(body)['fields'])
        self.assertIn('text_fr', body['highlight']['fields'])


# ---------------------------------------------------------------------------
# Integration tests: run against a real Elasticsearch if one is reachable at
# settings.PARLIAMENT_ES_URL (e.g. PARLIAMENT_ES_URL=http://localhost:9200).

def _es_available():
    try:
        return es_index.get_es_client().ping()
    except Exception:
        return False


TEST_ALIAS = 'parliament-test'

DOCS = [
    {
        'id': 'hansards.statement.1', 'django_ct': 'hansards.statement', 'django_id': '1',
        'doctype': 'debate', 'date': '2026-08-01T14:00:00Z', 'url': '/debates/2026/8/1/a-1/',
        'doc_url': '/debates/2026/8/1/', 'politician': 'Amélie Bélanger', 'politician_id': 'amelie-belanger',
        'party': 'Liberal', 'province': 'QC', 'topic_en': 'Taxation', 'procedural': False, 'wordcount': 40,
        'speaker': 'Amélie Bélanger',
        'text_en': 'The carbon tax rebate is a <b>good</b> thing for taxes generally.',
        'text_fr': "Le remboursement de la taxe sur le carbone est une bonne chose.",
    },
    {
        'id': 'hansards.statement.2', 'django_ct': 'hansards.statement', 'django_id': '2',
        'doctype': 'debate', 'date': '2016-08-01T14:00:00Z', 'url': '/debates/2016/8/1/b-1/',
        'doc_url': '/debates/2016/8/1/', 'politician': 'Bob Smith', 'politician_id': 'bob-smith',
        'party': 'Conservative', 'province': 'AB', 'topic_en': 'Taxation', 'procedural': False, 'wordcount': 40,
        'speaker': 'Bob Smith',
        'text_en': 'We taxed nothing. The rebate was never delivered.',
    },
    {
        'id': 'hansards.statement.3', 'django_ct': 'hansards.statement', 'django_id': '3',
        'doctype': 'committee', 'date': '2024-03-10T11:00:00Z', 'url': '/committees/finance/44-1/12/c-1/',
        'doc_url': '/committees/finance/44-1/12/', 'politician': 'Jane Witness', 'who_hocid': 999,
        'committee_slug': 'finance', 'committee_en': 'Finance', 'procedural': False, 'wordcount': 40,
        'speaker': 'Jane Witness',
        'text_en': 'Bill C-11, the Online Streaming Act, would change how streaming is regulated.',
    },
    {
        # Same words as the statement above, but procedural and dated later
        'id': 'hansards.statement.4', 'django_ct': 'hansards.statement', 'django_id': '4',
        'doctype': 'debate', 'date': '2026-08-02T14:00:00Z', 'url': '/debates/2026/8/2/speaker-1/',
        'doc_url': '/debates/2026/8/2/', 'politician': 'The Speaker', 'procedural': True, 'wordcount': 8,
        'speaker': 'The Speaker',
        'text_en': 'The streaming is regulated. Order, please.',
    },
    {
        'id': 'bills.bill.10', 'django_ct': 'bills.bill', 'django_id': '10',
        'doctype': 'bill', 'date': '2022-02-02T12:00:00Z', 'url': '/bills/44-1/C-11/',
        'number': 'C-11', 'session': '44-1', 'title_en': 'An Act to amend the Broadcasting Act',
        'topic_en': 'Online Streaming Act', 'title_key': ['online streaming act'],
        'boosted': 'Bill C-11', 'politician': 'Pablo Rodriguez',
        'politician_id': 'pablo-rodriguez', 'party': 'Liberal',
        'bill_text_en': 'This enactment amends the Broadcasting Act to add online undertakings.',
    },
    {
        'id': 'bills.bill.11', 'django_ct': 'bills.bill', 'django_id': '11',
        'doctype': 'bill', 'date': '2010-02-02T12:00:00Z', 'url': '/bills/40-3/C-11/',
        'number': 'C-11', 'session': '40-3', 'title_en': 'Balanced Refugee Reform Act',
        'topic_en': 'Balanced Refugee Reform Act', 'title_key': ['balanced refugee reform act'],
        'boosted': 'Bill C-11', 'party': 'Conservative',
        'bill_text_en': 'This enactment amends the Immigration and Refugee Protection Act.',
    },
    {
        'id': 'core.politician.5', 'django_ct': 'core.politician', 'django_id': '5',
        'doctype': 'mp', 'url': '/politicians/amelie-belanger/', 'politician': 'Amélie Bélanger',
        'party': 'Liberal', 'party_slug': 'Lib', 'province': 'QC', 'riding': 'Québec Centre',
        'riding_search': 'Québec Centre', 'boosted': 'Amélie Bélanger Liberal Party of Canada Liberal',
        'title_key': ['amelie belanger', 'quebec centre'],
    },
]


@unittest.skipUnless(_es_available(), "Elasticsearch not reachable")
@override_settings(PARLIAMENT_ES_INDEX=TEST_ALIAS)
class ElasticsearchIntegrationTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.es = es_index.get_es_client()
        with override_settings(PARLIAMENT_ES_INDEX=TEST_ALIAS):
            cls._delete_test_indices()
            cls.index_name = es_index.create_index(es_index.new_index_name(), client=cls.es, bulk_load=True)
            es_index.index_documents(DOCS, index=cls.index_name, client=cls.es)
            es_index.finish_bulk_load(cls.index_name, client=cls.es)
            es_index.swap_alias(cls.index_name, client=cls.es)

    @classmethod
    def _delete_test_indices(cls):
        for name in es_index.get_write_indices(cls.es):
            cls.es.indices.delete(index=name)

    @classmethod
    def tearDownClass(cls):
        cls._delete_test_indices()
        super().tearDownClass()

    def search(self, query, **kwargs):
        return SearchQuery(query, **kwargs)

    def urls(self, query, **kwargs):
        return [d['url'] for d in self.search(query, **kwargs).documents]

    def test_alias_and_write_indices(self):
        self.assertEqual(es_index.get_live_indices(self.es), [self.index_name])
        self.assertEqual(es_index.get_write_indices(self.es), [self.index_name])

    def test_stemming(self):
        urls = self.urls('taxes')
        self.assertIn('/debates/2026/8/1/a-1/', urls)   # "tax", "taxes"
        self.assertIn('/debates/2016/8/1/b-1/', urls)   # "taxed"

    def test_quoted_phrase_is_unstemmed(self):
        self.assertEqual(self.urls('"carbon tax"'), ['/debates/2026/8/1/a-1/'])
        self.assertIn('/debates/2016/8/1/b-1/', self.urls('taxed'))
        self.assertNotIn('/debates/2016/8/1/b-1/', self.urls('"taxes"'))
        self.assertEqual(self.urls('"rebate was never"'), ['/debates/2016/8/1/b-1/'])
        self.assertEqual(self.urls('"rebate is never"'), [])

    def test_all_terms_required(self):
        # Two terms: both needed, not either
        self.assertEqual(self.urls('rebate delivered'), ['/debates/2016/8/1/b-1/'])
        self.assertEqual(self.urls('rebate zebra'), [])
        # Longer queries may miss a quarter of their terms
        self.assertEqual(self.urls('rebate never delivered nonsense'), ['/debates/2016/8/1/b-1/'])
        self.assertEqual(self.urls('rebate never delivered nonsense', minimum_should_match='100%'), [])

    def test_operators(self):
        self.assertEqual(self.urls('rebate -carbon'), ['/debates/2016/8/1/b-1/'])
        self.assertEqual(self.urls('rebate -"never delivered"'), ['/debates/2026/8/1/a-1/'])
        self.assertEqual(self.urls('rebate NOT carbon'), ['/debates/2016/8/1/b-1/'])
        self.assertEqual(self.urls('rebate AND carbon'), ['/debates/2026/8/1/a-1/'])
        self.assertEqual(set(self.urls('rebate OR zebra')), {'/debates/2026/8/1/a-1/', '/debates/2016/8/1/b-1/'})
        self.assertEqual(set(self.urls('carbon | delivered')), {'/debates/2026/8/1/a-1/', '/debates/2016/8/1/b-1/'})
        self.assertEqual(self.urls('“carbon tax”'), ['/debates/2026/8/1/a-1/'])
        # Malformed syntax never raises
        self.search('"unbalanced (quote').documents
        self.search('AND OR ) (').documents

    def test_accent_folding(self):
        urls = self.urls('belanger')
        self.assertIn('/politicians/amelie-belanger/', urls)
        self.assertIn('/debates/2026/8/1/a-1/', urls)
        self.assertIn('/politicians/amelie-belanger/', self.urls('Bélanger'))
        self.assertIn('/politicians/amelie-belanger/', self.urls('"amelie belanger"'))

    def test_mp_ranks_first_for_name_query(self):
        docs = self.search('Amélie Bélanger').documents
        self.assertEqual(docs[0]['doctype'], 'mp')
        self.assertEqual(str(docs[0]['text']),
                         '<span class="tag partytag_lib">Liberal</span> MP for Québec Centre')
        # ...but only if the whole query fits the name
        self.assertNotIn('/politicians/amelie-belanger/', self.urls('Bélanger rebate'))

    def test_riding_name_finds_mp(self):
        self.assertEqual(self.urls('"Québec Centre"'), ['/politicians/amelie-belanger/'])
        self.assertEqual(self.urls('quebec centre')[0], '/politicians/amelie-belanger/')
        # ...but a riding word alone doesn't put MPs above the statements
        self.assertEqual(self.urls('taxes centre'), [])

    def test_proximity_match_highlights_terms_not_the_span(self):
        doc = [d for d in self.search('streaming regulated').documents if d['url'] == '/committees/finance/44-1/12/c-1/'][0]
        self.assertIn('<em>streaming</em>', doc['text'])
        self.assertIn('<em>regulated</em>', doc['text'])
        self.assertNotIn('<em>Streaming Act, would', doc['text'])

    def test_bill_number_query(self):
        urls = self.urls('C-11')
        # Both C-11s first, newest first; then the statement mentioning it
        self.assertEqual(urls[:2], ['/bills/44-1/C-11/', '/bills/40-3/C-11/'])
        self.assertIn('/committees/finance/44-1/12/c-1/', urls)
        self.assertEqual(self.urls('c11')[:2], ['/bills/44-1/C-11/', '/bills/40-3/C-11/'])
        self.assertIn('/committees/finance/44-1/12/c-1/', self.urls('"bill c-11"'))

    def test_bill_number_with_other_terms(self):
        self.assertEqual(self.urls('C-11 streaming')[0], '/bills/44-1/C-11/')

    def test_exact_bill_title_wins_despite_age(self):
        self.assertEqual(self.urls('Online Streaming Act')[0], '/bills/44-1/C-11/')
        self.assertEqual(self.urls('online streaming act')[0], '/bills/44-1/C-11/')

    def test_recency(self):
        docs = self.search('rebate').documents
        self.assertEqual([d['url'] for d in docs], ['/debates/2026/8/1/a-1/', '/debates/2016/8/1/b-1/'])
        self.assertGreater(docs[0]['score'], docs[1]['score'])

    def test_procedural_and_short_statements_rank_low(self):
        # Newer and shorter, but procedural: below the substantive one
        self.assertEqual(self.urls('streaming regulated'),
                         ['/committees/finance/44-1/12/c-1/', '/debates/2026/8/2/speaker-1/'])

    def test_highlighting_escapes_html(self):
        doc = self.search('carbon tax').documents[0]
        self.assertIn('<em>carbon</em> <em>tax</em>', doc['text'])
        self.assertIn('&lt;b&gt;good&lt;', doc['text'])
        self.assertNotIn('<b>', doc['text'])
        self.assertNotIn('full_text', doc)

    def test_quoted_phrase_is_highlighted(self):
        doc = self.search('"rebate was never"').documents[0]
        self.assertIn('<em>rebate was never</em>', doc['text'])

    def test_bill_text_is_highlighted(self):
        doc = [d for d in self.search('broadcasting undertakings').documents if d['doctype'] == 'bill'][0]
        self.assertIn('<em>', doc['text'])

    def test_no_match_snippet_for_speaker_match(self):
        doc = [d for d in self.search('Bob Smith').documents if d['url'] == '/debates/2016/8/1/b-1/'][0]
        self.assertIn('We taxed nothing', doc['text'])

    def test_full_text(self):
        doc = self.search('carbon tax', full_text=True).documents[0]
        self.assertIn('<em>', doc['text'])
        self.assertEqual(doc['full_text'], DOCS[0]['text_en'])

    def test_filters(self):
        self.assertEqual(self.urls('tax Party: "Conservative"'), ['/debates/2016/8/1/b-1/'])
        self.assertEqual(self.urls('tax Type: "bill"'), [])
        self.assertEqual(self.urls('Type: "bill"'), ['/bills/44-1/C-11/', '/bills/40-3/C-11/'])
        self.assertEqual(self.urls('Witness: "999"'), ['/committees/finance/44-1/12/c-1/'])
        self.assertEqual(self.urls('MP: "bob-smith"'), ['/debates/2016/8/1/b-1/'])
        self.assertEqual(self.urls('Committee: "finance"'), ['/committees/finance/44-1/12/c-1/'])
        self.assertEqual(self.urls('Document: "/debates/2016/8/1/"'), ['/debates/2016/8/1/b-1/'])
        self.assertEqual(self.urls('Date: "2016-08"'), ['/debates/2016/8/1/b-1/'])
        self.assertEqual(self.urls('Date: "2016-08-01"'), ['/debates/2016/8/1/b-1/'])
        self.assertEqual(self.urls('Date: "2016-08-02"'), [])
        self.assertEqual(self.urls('Date: "2016-01 to 2024-12"', user_params={'sort': 'date asc'}),
                         ['/debates/2016/8/1/b-1/', '/bills/44-1/C-11/', '/committees/finance/44-1/12/c-1/'])

    def test_ids(self):
        self.assertEqual(self.urls('tax', ids=['hansards.statement.2', 'bills.bill.10']), ['/debates/2016/8/1/b-1/'])

    def test_sorting(self):
        self.assertEqual(self.urls('tax', user_params={'sort': 'date asc'}),
                         ['/debates/2016/8/1/b-1/', '/debates/2026/8/1/a-1/'])
        self.assertEqual(self.urls('tax', user_params={'sort': 'date desc'}),
                         ['/debates/2026/8/1/a-1/', '/debates/2016/8/1/b-1/'])

    def test_pagination(self):
        q = self.search('Type: "bill"', start=1, limit=1)
        self.assertEqual(q.hits, 2)
        self.assertEqual([d['url'] for d in q.documents], ['/bills/40-3/C-11/'])

    def test_dates_are_datetimes(self):
        doc = self.search('carbon').documents[0]
        self.assertEqual(doc['date'], datetime.datetime(2026, 8, 1, 14, 0))

    def test_facets(self):
        q = self.search('tax', facet=True)
        self.assertEqual(q.facet_fields['party'], ['Conservative', 1, 'Liberal', 1])
        self.assertEqual(q.facet_fields['doctype'], ['debate', 2])
        self.assertEqual(q.facet_fields['politician'], ['Amélie Bélanger', 1, 'Bob Smith', 1])
        counts = dict(q.date_counts)
        self.assertEqual(counts[2016], 1)
        self.assertEqual(counts[2026], 1)
        self.assertEqual(counts[2020], 0)
        self.assertEqual(min(counts), 1994)
        self.assertEqual(q.discontinuity, 2006)

    def test_multiselect_facets(self):
        q = self.search('tax Party: "Liberal"', facet=True)
        self.assertEqual(q.hits, 1)
        # The party facet still shows the other party as an option...
        self.assertEqual(q.facet_fields['party'], ['Conservative', 1, 'Liberal', 1])
        # ...but other facets respect the party filter
        self.assertEqual(q.facet_fields['politician'], ['Amélie Bélanger', 1])
        self.assertEqual(dict(q.date_counts)[2016], 0)

    def test_committee_facet_range(self):
        q = self.search('C-11 Type: "committee"', facet=True)
        self.assertTrue(q.committees_only)
        self.assertEqual(min(dict(q.date_counts)), 2006)
        self.assertIsNone(q.discontinuity)

    def test_french(self):
        self.assertEqual(self.urls('remboursement', language='fr'), ['/debates/2026/8/1/a-1/'])
        doc = self.search('taxe carbone', language='fr').documents[0]
        self.assertIn('<em>taxe', doc['text'])
        self.assertEqual(self.urls('rebate', language='fr'), [])

    def test_suggestions(self):
        response = self.es.search(index=TEST_ALIAS, body=build_suggest_body('carbn tax'))
        self.assertEqual(apply_suggestions('carbn tax', response), 'carbon tax')
        # Nothing to suggest for words that exist, however rare
        response = self.es.search(index=TEST_ALIAS, body=build_suggest_body('Belanger rebate'))
        self.assertIsNone(apply_suggestions('Belanger rebate', response))
        # The query object only offers a suggestion that finds enough results
        self.assertIsNone(self.search('carbn tax').suggestion)

    def test_far_future_date_is_neither_new_nor_graphed(self):
        es_index.index_documents([{
            'id': 'hansards.statement.4043', 'django_ct': 'hansards.statement', 'django_id': '4043',
            'doctype': 'debate', 'date': '4043-03-22T14:00:00Z', 'url': '/debates/4043/3/22/a-1/',
            'politician': 'Time Traveller', 'text_en': 'The carbon tax rebate, from the future.',
            'procedural': False, 'wordcount': 40,
        }], client=self.es)
        self.es.indices.refresh(index=TEST_ALIAS)
        try:
            q = self.search('"carbon tax"', facet=True)
            self.assertEqual(q.documents[0]['url'], '/debates/2026/8/1/a-1/')
            self.assertLessEqual(max(dict(q.date_counts)), datetime.date.today().year)
        finally:
            es_index.delete_documents(['hansards.statement.4043'], client=self.es)
            self.es.indices.refresh(index=TEST_ALIAS)

    def test_incremental_update_and_delete(self):
        es_index.index_documents([{
            'id': 'hansards.statement.99', 'django_ct': 'hansards.statement', 'django_id': '99',
            'doctype': 'debate', 'date': '2026-09-01T14:00:00Z', 'url': '/debates/2026/9/1/z-1/',
            'text_en': 'A wholly unique zebra statement.', 'procedural': False, 'wordcount': 40,
        }], client=self.es)
        self.es.indices.refresh(index=TEST_ALIAS)
        self.assertEqual(self.urls('zebra'), ['/debates/2026/9/1/z-1/'])
        es_index.delete_documents(['hansards.statement.99', 'hansards.statement.does-not-exist'], client=self.es)
        self.es.indices.refresh(index=TEST_ALIAS)
        self.assertEqual(self.urls('zebra'), [])


class CollapseTasksTests(SimpleTestCase):

    def _t(self, action, identifier):
        return IndexingTask(action=action, identifier=identifier)

    def test_last_action_wins(self):
        tasks = [
            self._t('update', 'hansards.statement.1'),
            self._t('update', 'hansards.statement.1'),
            self._t('update', 'hansards.statement.2'),
            self._t('delete', 'hansards.statement.2'),
            self._t('delete', 'bills.bill.3'),
            self._t('update', 'bills.bill.3'),
        ]
        updates, deletes = collapse_tasks(tasks)
        self.assertEqual(set(updates), {'hansards.statement.1', 'bills.bill.3'})
        self.assertIs(updates['hansards.statement.1'], tasks[1])
        self.assertEqual(deletes, {'hansards.statement.2'})

    def test_empty(self):
        self.assertEqual(collapse_tasks([]), ({}, set()))
