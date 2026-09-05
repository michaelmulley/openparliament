"""Search tools that interface with Elasticsearch.

`build_search_body` is a pure function that turns a parsed user query into an
Elasticsearch request body, so ranking behaviour can be unit-tested without a
running cluster. `SearchQuery` wraps it and exposes results, facets and
suggestions to the views, the feed and the alerts.

How a query is interpreted and ranked
-------------------------------------
- Terms are stemmed and accent-folded; quoted phrases match the unstemmed
  `.exact` subfields. -term and -"phrase" exclude. AND / OR / NOT written as
  words (and `|`, `+`) are operators; anything else is plain text and can
  never cause a syntax error.
- Every term is required for queries of up to three terms; longer queries may
  miss a quarter of theirs. With four million short documents, recall is
  never the problem.
- Relevance is BM25 across statement text, heading, bill title, speaker and
  the `boosted` field (MP names, bill numbers and short titles), with a
  bonus for terms appearing close together.
- Recency is a bounded multiplier: current material scores fully, old
  material no less than RECENCY_FLOOR of its relevance.
- Procedural statements and very short ones are discounted.
- A query that is only a bill number lists every session's bill newest
  first, then everything mentioning it, newest first.
"""

import datetime
import re

from django.conf import settings
from django.utils.safestring import mark_safe

from parliament.core.utils import memoize_property
from parliament.search.es_index import (get_alias_name, get_es_client,
                                        index_documents, delete_documents)  # noqa: F401 (indexing interface)
from parliament.search.utils import (BaseSearchQuery, parse_date_filter,
                                     politician_result_html, title_key)

# Fields matched by unquoted terms. Quoted phrases are matched against the
# unstemmed `.exact` subfield of each (via quote_field_suffix).
QUERY_FIELDS = {
    'en': ['text_en', 'bill_text_en', 'topic_en^1.5', 'title_en^1.5', 'speaker', 'riding_search', 'boosted^3'],
    'fr': ['text_fr', 'bill_text_fr', 'topic_fr^1.5', 'title_fr^1.5', 'speaker', 'riding_search', 'boosted^3'],
}
HIGHLIGHT_FIELDS = {'en': ['text_en', 'bill_text_en'], 'fr': ['text_fr', 'bill_text_fr']}
LANGUAGE_FIELDS = ('text', 'topic', 'title', 'committee')

# All terms required up to three; beyond that, a quarter may be missing.
MINIMUM_SHOULD_MATCH = '3<-25%'

# Recency multiplier: 1.0 now, decaying by half every RECENCY_HALF_LIFE_YEARS
# towards RECENCY_FLOOR. MPs have no date: sitting MPs get 1.0, former MPs
# decay from the year they left.
RECENCY_FLOOR = 0.35
RECENCY_HALF_LIFE_YEARS = 4.0

# Discounts on statements that are rarely what anyone is looking for
PROCEDURAL_WEIGHT = 0.2
SHORT_STATEMENT_WORDS = 30
SHORT_STATEMENT_WEIGHT = 0.6

# Proximity bonuses: terms adjacent, and terms within a sentence or two
PHRASE_BOOSTS = ((2, 2.0), (40, 1.0))  # (slop, boost)

# A query that is exactly a bill's short title, an MP's name or a riding's
# name should find that bill or MP first, however old: this multiplies the
# score, after the recency decay. Large, because terms in the small fields
# only MPs and bills have carry less weight than the same terms in Hansard.
EXACT_MATCH_WEIGHT = 10.0

# Bill-number-only queries: score = BILL_NUMBER_WEIGHT for the bills
# themselves, plus a recency term, instead of text relevance.
BILL_NUMBER_WEIGHT = 1e6

# Filters carry tags; a facet excludes the filters carrying its tag so that
# it keeps showing the alternatives (multi-select faceting).
FILTER_TAGS = {
    'politician': 'fperson',
    'politician_id': 'fperson',
    'who_hocid': 'fperson',
    'party': 'fparty',
    'province': 'fprovince',
    'doctype': 'fdoctype',
    'date': 'fdate',
    'doc_url': 'fdate',
    'committee_slug': 'fcommittee',
}
FACETS = {  # facet name -> (field, tag it ignores)
    'politician': ('politician', 'fperson'),
    'province': ('province', 'fprovince'),
    'party': ('party', 'fparty'),
    'doctype': ('doctype', 'fdoctype'),
}
DATE_FACET_EXCLUDES = 'fdate'
FACET_LIMIT = 13

HIGHLIGHT_FRAGMENT_SIZE = 280

# Offer a spelling suggestion when a query finds fewer results than this
SUGGEST_BELOW_HITS = 5

# Bill numbers in queries, e.g. "C-11", "c11", "S-5"
r_bill_number = re.compile(r'(?<![\w-])([CcSs])-?(\d{1,4})(?![\w-])')
r_only_bill_number = re.compile(r'\s*(?:bill\s+)?[CcSs]-?\d{1,4}\s*', re.IGNORECASE)
# Query syntax characters, stripped before building the phrase-proximity boost
r_query_syntax = re.compile(r'["+|*()~\\]|(?<!\w)-')
# Negated terms and phrases: -word, -"a phrase"
r_negation = re.compile(r'(?:^|(?<=\s))-("[^"]+"|\S+)')
# Boolean operators written as words (uppercase only, so that "and" in a
# phrase of ordinary text stays ordinary text)
r_and_word = re.compile(r'(?<!\S)(?:AND|&)(?!\S)')
r_or_word = re.compile(r'(?<!\S)OR(?!\S)')
r_not_word = re.compile(r'(?<!\S)NOT\s+')

CURLY_QUOTES = str.maketrans({'“': '"', '”': '"', '„': '"', '«': '"', '»': '"',
                              '‘': "'", '’': "'"})

SIMPLE_QUERY_FLAGS = 'OR|AND|NOT|PREFIX|PHRASE|PRECEDENCE|ESCAPE|WHITESPACE'


def normalize_query(query: str) -> tuple[str, bool]:
    """Straightens curly quotes and turns AND / OR / NOT written as words into
    simple_query_string operators. Returns (query, has_explicit_operators):
    with explicit operators, whitespace means AND and the minimum-match rule
    doesn't apply, so that "a OR b OR c" means what it says."""
    q = query.translate(CURLY_QUOTES)
    explicit = bool(r_and_word.search(q) or r_or_word.search(q) or r_not_word.search(q) or '|' in q)
    if explicit:
        q = r_and_word.sub(' ', q)
        q = r_or_word.sub('|', q)
        q = r_not_word.sub('-', q)
    return ' '.join(q.split()), explicit


def split_negations(query: str) -> tuple[str, list[str]]:
    """Separates -term and -"phrase" exclusions from the rest of a query.

    simple_query_string reads "rebate -carbon" as "rebate OR NOT carbon";
    we (like everyone's intuition) want it to mean "rebate, and not carbon",
    so exclusions are applied as separate must_not clauses.
    """
    negated = [m.group(1) for m in r_negation.finditer(query)]
    remainder = ' '.join(r_negation.sub('', query).split())
    return remainder, negated


def _negation_clause(term: str, fields: list[str]) -> dict:
    bare_fields = [f.split('^')[0] for f in fields]
    if term.startswith('"') and term.endswith('"') and len(term) > 2:
        return {'multi_match': {'query': term[1:-1], 'type': 'phrase',
                                'fields': [f + '.exact' for f in bare_fields]}}
    return {'multi_match': {'query': term, 'fields': bare_fields}}


def find_bill_numbers(query: str) -> list[str]:
    """Normalized ('c-11') bill numbers mentioned in a query."""
    return [f"{m.group(1).lower()}-{int(m.group(2))}" for m in r_bill_number.finditer(query)]


def _filter_clause(field: str, value: str) -> dict | None:
    if field == 'date':
        date_range = parse_date_filter(value)
        if not date_range:
            return None
        start, end = date_range
        return {'range': {'date': {'gte': start.isoformat(), 'lt': end.isoformat()}}}
    if field == 'who_hocid':
        if not value.isdigit():
            return None
        return {'term': {field: int(value)}}
    return {'term': {field: value}}


def _recency_multiplier(now: datetime.datetime) -> dict:
    return {
        'script_score': {
            'script': {
                # abs(): a document mistakenly dated far in the future should
                # rank like an old one, not a brand-new one.
                'source': (
                    "double years;"
                    "if (doc['date'].size() > 0) {"
                    "  years = Math.abs(params.now - doc['date'].value.toInstant().toEpochMilli()) / 3.156e10;"
                    "} else if (doc['end_year'].size() > 0) {"
                    "  years = Math.max(0, params.now_year - doc['end_year'].value);"
                    "} else { return 1.0; }"
                    "return params.floor + (1.0 - params.floor) * Math.exp(-0.6931 * years / params.half_life);"
                ),
                'params': {
                    'now': int(now.timestamp() * 1000),
                    'now_year': now.year,
                    'floor': RECENCY_FLOOR,
                    'half_life': RECENCY_HALF_LIFE_YEARS,
                },
            }
        }
    }


def _recency_additive(now: datetime.datetime) -> dict:
    """For bill-number queries: newer first, regardless of text relevance."""
    return {
        'script_score': {
            'script': {
                'source': (
                    "if (doc['date'].size() == 0) { return 0.0; }"
                    "double years = Math.abs(params.now - doc['date'].value.toInstant().toEpochMilli()) / 3.156e10;"
                    "return 1000.0 / (years + 1.0);"
                ),
                'params': {'now': int(now.timestamp() * 1000)},
            }
        }
    }


def build_search_body(bare_query: str, filters: dict[str, str], *,
                      start: int = 0, limit: int = 15, sort: str = 'score desc',
                      facet: bool = False, full_text: bool = False,
                      minimum_should_match: str = MINIMUM_SHOULD_MATCH, language: str = 'en',
                      now: datetime.datetime | None = None,
                      date_facet_start: int = 1994) -> dict:
    """Build an Elasticsearch request body.

    `filters` maps index field names (politician_id, party, date, ...) to
    the user-supplied filter value.
    """
    now = now or datetime.datetime.now().replace(minute=0, second=0, microsecond=0)
    fields = QUERY_FIELDS[language]

    # -- Filters: those a facet needs to ignore go in post_filter, the rest
    #    narrow the query itself.
    excludable_tags = {tag for _, tag in FACETS.values()} | {DATE_FACET_EXCLUDES}
    query_filters, post_filters = [], []  # (tag, clause)
    for field, value in filters.items():
        clause = _filter_clause(field, value)
        if clause is None:
            continue
        tag = FILTER_TAGS.get(field, 'f' + field)
        if facet and tag in excludable_tags:
            post_filters.append((tag, clause))
        else:
            query_filters.append((tag, clause))

    # -- The text query
    normalized, explicit_operators = normalize_query(bare_query)
    positive_query, negated = split_negations(normalized)
    must, should = [], []
    must_not = [_negation_clause(term, fields) for term in negated]
    only_bill_number = False
    bill_numbers = []
    if positive_query:
        sqs = {
            'query': positive_query,
            'fields': fields,
            'quote_field_suffix': '.exact',
            'flags': SIMPLE_QUERY_FLAGS,
        }
        if explicit_operators:
            sqs['default_operator'] = 'and'
        else:
            sqs['default_operator'] = 'or'
            sqs['minimum_should_match'] = minimum_should_match
        must.append({'simple_query_string': sqs})

        # Reward documents where the terms appear close together
        phrase_text = ' '.join(r_query_syntax.sub(' ', positive_query).split())
        if not explicit_operators and len(phrase_text.split()) > 1:
            for slop, boost in PHRASE_BOOSTS:
                should.append({'multi_match': {
                    'query': phrase_text, 'type': 'phrase', 'slop': slop,
                    'fields': fields, 'boost': boost,
                }})

        # A query mentioning a bill number should float the bills themselves
        # towards the top. A query that *is* a bill number gets every
        # session's C-11 first, newest first, then everything mentioning it,
        # newest first: text relevance is meaningless for such a query.
        bill_numbers = find_bill_numbers(positive_query)
        only_bill_number = bool(bill_numbers) and bool(r_only_bill_number.fullmatch(positive_query))
        if bill_numbers and not only_bill_number:
            should.append({'terms': {'number': bill_numbers, 'boost': 50}})

    bool_query = {}
    if must:
        bool_query['must'] = must
    if should:
        bool_query['should'] = should
    if must_not:
        bool_query['must_not'] = must_not
    if query_filters:
        bool_query['filter'] = [clause for _, clause in query_filters]
    query = {'bool': bool_query} if bool_query else {'match_all': {}}

    if not positive_query and sort == 'score desc':
        # Nothing to rank by: newest first
        sort = 'date desc'

    if positive_query and sort == 'score desc':
        if only_bill_number:
            query = {'function_score': {
                'query': query,
                'functions': [
                    {'filter': {'terms': {'number': bill_numbers}}, 'weight': BILL_NUMBER_WEIGHT},
                    _recency_additive(now),
                ],
                'score_mode': 'sum',
                'boost_mode': 'replace',
            }}
        else:
            functions = [
                _recency_multiplier(now),
                {'filter': {'term': {'procedural': True}}, 'weight': PROCEDURAL_WEIGHT},
                {'filter': {'range': {'wordcount': {'lt': SHORT_STATEMENT_WORDS}}},
                 'weight': SHORT_STATEMENT_WEIGHT},
            ]
            exact_key = title_key(phrase_text) if not explicit_operators else None
            if exact_key:
                functions.append({'filter': {'term': {'title_key': exact_key}}, 'weight': EXACT_MATCH_WEIGHT})
            query = {'function_score': {
                'query': query,
                'functions': functions,
                'score_mode': 'multiply',
                'boost_mode': 'multiply',
            }}

    body = {
        'from': start,
        'size': limit,
        'track_total_hits': True,
        'query': query,
    }

    if sort != 'score desc':
        sort_field, sort_dir = sort.split()
        body['sort'] = [{sort_field: {'order': sort_dir, 'missing': '_last'}}]

    if post_filters:
        body['post_filter'] = {'bool': {'filter': [clause for _, clause in post_filters]}}

    if not full_text:
        body['_source'] = {'excludes': ['text_*', 'bill_text_*']}

    body['highlight'] = {
        'type': 'unified',
        # Highlight the terms and quoted phrases only: a sloppy proximity
        # match would be marked as one span from its first term to its last.
        **({'highlight_query': {'bool': {'must': must}}} if must else {}),
        # matched_fields lets quoted phrases, matched on the unstemmed
        # subfield, be highlighted in the stemmed parent field.
        'fields': {f: {'matched_fields': [f, f + '.exact']} for f in HIGHLIGHT_FIELDS[language]},
        'fragment_size': HIGHLIGHT_FRAGMENT_SIZE,
        'number_of_fragments': 1,
        'no_match_size': HIGHLIGHT_FRAGMENT_SIZE,
        'pre_tags': ['<em>'],
        'post_tags': ['</em>'],
        'encoder': 'html',
        'require_field_match': True,
    }

    if facet:
        aggs = {}

        def facet_filter(excluded_tag):
            return {'bool': {'filter': [
                clause for tag, clause in post_filters if tag != excluded_tag
            ]}}

        for name, (field, excluded_tag) in FACETS.items():
            aggs[name] = {
                'filter': facet_filter(excluded_tag),
                'aggs': {'values': {'terms': {
                    'field': field, 'size': FACET_LIMIT, 'min_doc_count': 1,
                }}},
            }
        aggs['date'] = {
            'filter': facet_filter(DATE_FACET_EXCLUDES),
            'aggs': {'values': {'date_histogram': {
                'field': 'date',
                'calendar_interval': 'year',
                'format': 'yyyy',
                'min_doc_count': 0,
                'extended_bounds': {'min': str(date_facet_start), 'max': str(now.year)},
                # ...and nothing outside them, however a document is dated.
                # (Bounds are instants: "2027" is the start of 2027.)
                'hard_bounds': {'min': str(date_facet_start), 'max': str(now.year + 1)},
            }}},
        }
        body['aggs'] = aggs

    return body


def build_suggest_body(text: str, language: str = 'en') -> dict:
    """Spelling suggestions for the words of a query that don't occur in the
    index at all (so a rare but real name is never "corrected")."""
    return {
        'size': 0,
        'suggest': {
            'terms': {
                'text': text,
                'term': {
                    'field': f'{HIGHLIGHT_FIELDS[language][0]}.exact',
                    'suggest_mode': 'missing',
                    'string_distance': 'damerau_levenshtein',
                    'max_edits': 2,
                    'prefix_length': 1,
                    'min_word_length': 4,
                    'size': 1,
                },
            }
        },
    }


def apply_suggestions(text: str, suggest_response: dict) -> str | None:
    """Rewrites `text` with the suggester's top option for each misspelled
    word, or returns None if it had nothing to suggest."""
    entries = [e for e in suggest_response.get('suggest', {}).get('terms', []) if e.get('options')]
    if not entries:
        return None
    for entry in sorted(entries, key=lambda e: e['offset'], reverse=True):
        replacement = entry['options'][0]['text']
        original = text[entry['offset']:entry['offset'] + entry['length']]
        if original[:1].isupper():
            replacement = replacement.capitalize()
        text = text[:entry['offset']] + replacement + text[entry['offset'] + entry['length']:]
    return text


def _parse_date(value: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(value.replace('Z', ''))


def _process_hit(hit: dict, language: str, full_text: bool) -> dict:
    doc = hit['_source']
    doc['id'] = hit['_id']
    doc['score'] = hit.get('_score')
    for datefield in ('date', 'time'):
        if doc.get(datefield):
            doc[datefield] = _parse_date(doc[datefield])
    for field in LANGUAGE_FIELDS:
        value = doc.get(f'{field}_{language}') or doc.get(f'{field}_en')
        if value is not None:
            doc[field] = value
    if doc.get('doctype') == 'mp':
        doc['text'] = mark_safe(politician_result_html(
            doc.get('party', ''), doc.get('party_slug', ''),
            doc.get('riding', ''), doc.get('end_year')))
    else:
        highlights = hit.get('highlight', {})
        highlight = next((highlights[f] for f in HIGHLIGHT_FIELDS[language] if highlights.get(f)), None)
        if highlight:
            if full_text and doc.get('text'):
                doc['full_text'] = doc['text']
            doc['text'] = mark_safe(highlight[0])
        else:
            doc.setdefault('text', '')
    return doc


class SearchResults:

    def __init__(self, response: dict, language: str, full_text: bool):
        self.hits = response['hits']['total']['value']
        self.docs = [_process_hit(h, language, full_text) for h in response['hits']['hits']]
        self.aggregations = response.get('aggregations', {})

    @property
    def facet_fields(self) -> dict[str, list]:
        """Facet counts as a flat list per field: {'party': [value, count, ...]}"""
        result = {}
        for name in FACETS:
            flat = []
            for bucket in self.aggregations.get(name, {}).get('values', {}).get('buckets', []):
                flat.extend([bucket['key'], bucket['doc_count']])
            result[name] = flat
        return result

    @property
    def date_counts(self) -> list[tuple[int, int]]:
        buckets = self.aggregations.get('date', {}).get('values', {}).get('buckets', [])
        return [(int(b['key_as_string']), b['doc_count']) for b in buckets]


class SearchQuery(BaseSearchQuery):
    """Converts a user search query into an Elasticsearch request, and
    gets the results."""

    ALLOWABLE_OPTIONS = {
        'sort': ['score desc', 'date asc', 'date desc'],
    }

    ALLOWABLE_FILTERS = {
        'Party': 'party',
        'Province': 'province',
        'Person': 'politician',
        'MP': 'politician_id',
        'Witness': 'who_hocid',
        'Committee': 'committee_slug',
        'Date': 'date',
        'Type': 'doctype',
        'Document': 'doc_url'
    }

    def __init__(self, query, start=0, limit=15, user_params={},
                 facet=False, full_text=False, minimum_should_match=MINIMUM_SHOULD_MATCH,
                 language=None):
        super().__init__(query)
        self.start = start
        self.limit = limit
        self.user_params = user_params  # request.GET, basically
        self.facet = facet
        self.full_text = full_text
        self.minimum_should_match = minimum_should_match
        self.language = language or settings.LANGUAGE_CODE[:2]
        if self.language not in QUERY_FIELDS:
            self.language = 'en'

    @property
    def committees_only(self) -> bool:
        return 'Committee' in self.filters or self.filters.get('Type') == 'committee'

    @property
    def committees_maybe(self) -> bool:
        return 'Type' not in self.filters or self.committees_only

    @property
    @memoize_property
    def validated_user_params(self):
        p = {}
        for opt in self.ALLOWABLE_OPTIONS:
            if opt in self.user_params and self.user_params[opt] in self.ALLOWABLE_OPTIONS[opt]:
                p[opt] = self.user_params[opt]
        return p

    @property
    def index_filters(self) -> dict[str, str]:
        return {self.ALLOWABLE_FILTERS[name]: value for name, value in self.filters.items()}

    def get_search_body(self, bare_query=None) -> dict:
        return build_search_body(
            self.bare_query if bare_query is None else bare_query, self.index_filters,
            start=self.start, limit=self.limit,
            sort=self.validated_user_params.get('sort', 'score desc'),
            facet=self.facet, full_text=self.full_text,
            minimum_should_match=self.minimum_should_match,
            language=self.language,
            date_facet_start=2006 if self.committees_only else 1994,
        )

    @property
    def results(self) -> SearchResults:
        if not getattr(self, '_results', None):
            response = get_es_client().search(index=get_alias_name(), body=self.get_search_body())
            self._results = SearchResults(response, self.language, self.full_text)
        return self._results

    @property
    def hits(self):
        return self.results.hits

    @property
    def documents(self):
        return self.results.docs

    @property
    def facet_fields(self):
        return self.results.facet_fields if self.facet else None

    @property
    @memoize_property
    def date_counts(self):
        if not self.facet:
            return []
        counts = self.results.date_counts
        if self.committees_only:
            # If we're searching only committees, we by definition won't have
            # results before 2006, so let's take them off of the graph.
            counts = [c for c in counts if c[0] >= 2006]
        return counts

    @property
    def discontinuity(self):
        if self.results and self.committees_maybe and not self.committees_only:
            return 2006
        return None

    @property
    @memoize_property
    def suggestion(self) -> str | None:
        """A corrected version of the query, if it found few results, some
        of its words are misspelled, and the correction does better."""
        if not self.bare_query or self.hits >= SUGGEST_BELOW_HITS:
            return None
        client = get_es_client()
        response = client.search(index=get_alias_name(),
                                 body=build_suggest_body(self.bare_query, self.language))
        suggested = apply_suggestions(self.bare_query, response)
        if not suggested or suggested == self.bare_query:
            return None
        count = client.count(index=get_alias_name(), query=self.get_search_body(suggested)['query'])['count']
        if count <= self.hits or count < SUGGEST_BELOW_HITS:
            return None
        return (suggested + (' ' if self.filters else '') + ' '.join(
            '%s: "%s"' % (key, self.filters[key]) for key in sorted(self.filters))).strip()
