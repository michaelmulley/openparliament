"""Elasticsearch index definition and management.

The live index is reached through an alias (settings.PARLIAMENT_ES_INDEX,
"parliament" by default). Concrete indices are named "<alias>-<timestamp>",
which lets `rebuild_search_index` build a fresh index from the database in
the background and then swap the alias atomically.
"""

import datetime
import logging

from django.conf import settings

from elasticsearch import Elasticsearch, helpers

logger = logging.getLogger(__name__)

LANGUAGES = ('en', 'fr')

def get_es_client() -> Elasticsearch:
    return Elasticsearch(settings.PARLIAMENT_ES_URL, request_timeout=60)


def get_alias_name() -> str:
    return getattr(settings, 'PARLIAMENT_ES_INDEX', 'parliament')


# "Bill C-11" would otherwise be tokenized as "c" and "11". Fold bill numbers
# into a single token at both index and query time, so "c-11" matches exactly
# what it should, in bill records and in Hansard text alike.
BILL_NUMBER_CHAR_FILTER = {
    "type": "pattern_replace",
    "pattern": r"\b([CcSs])-(\d{1,4})\b",
    "replacement": "$1$2",
}

ANALYSIS = {
    "char_filter": {
        "bill_number": BILL_NUMBER_CHAR_FILTER,
    },
    "normalizer": {
        "lowercase": {"type": "custom", "filter": ["lowercase"]},
    },
    "filter": {
        "english_possessive": {"type": "stemmer", "language": "possessive_english"},
        "english_stop": {"type": "stop", "stopwords": "_english_"},
        # kstem: much less aggressive than Porter
        "english_stem": {"type": "stemmer", "language": "light_english"},
        "french_elision": {
            "type": "elision",
            "articles_case": True,
            "articles": ["l", "m", "t", "qu", "n", "s", "j", "d", "c",
                         "jusqu", "quoiqu", "lorsqu", "puisqu"],
        },
        "french_stop": {"type": "stop", "stopwords": "_french_"},
        "french_stem": {"type": "stemmer", "language": "light_french"},
    },
    "analyzer": {
        # Stemmed, accent-folded: what unquoted query terms match against.
        "en_text": {
            "tokenizer": "standard",
            "char_filter": ["bill_number"],
            "filter": ["english_possessive", "lowercase", "asciifolding",
                       "english_stop", "english_stem"],
        },
        # Unstemmed: what quoted phrases match against (the `.exact` subfields).
        "en_exact": {
            "tokenizer": "standard",
            "char_filter": ["bill_number"],
            "filter": ["english_possessive", "lowercase", "asciifolding"],
        },
        "fr_text": {
            "tokenizer": "standard",
            "char_filter": ["bill_number"],
            "filter": ["french_elision", "lowercase", "french_stop",
                       "french_stem", "asciifolding"],
        },
        "fr_exact": {
            "tokenizer": "standard",
            "char_filter": ["bill_number"],
            "filter": ["french_elision", "lowercase", "asciifolding"],
        },
    },
}

INDEX_SETTINGS = {
    "index": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "codec": "best_compression",
    },
    "analysis": ANALYSIS,
}


def _searchable_text(lang: str, highlight: bool = False, norms: bool = False) -> dict:
    """A text field searched by unquoted terms via its stemmed analyzer, and
    by quoted phrases via the unstemmed `.exact` subfield.

    Length normalization (norms) is off by default: a statement that keeps
    returning to a subject is more about it, and BM25's norms would favour
    the shortest mention instead."""
    d = {
        "type": "text",
        "analyzer": f"{lang}_text",
        "norms": norms,
        "fields": {
            "exact": {"type": "text", "analyzer": f"{lang}_exact", "norms": norms},
        },
    }
    if highlight:
        # Postings offsets make the unified highlighter fast on long texts,
        # and let phrase matches on the .exact subfield be highlighted in
        # the parent field (matched_fields).
        d["index_options"] = "offsets"
        d["fields"]["exact"]["index_options"] = "offsets"
    return d


def _display_only() -> dict:
    """Stored in _source for display, never searched or aggregated."""
    return {"type": "keyword", "index": False, "doc_values": False}


def _keyword() -> dict:
    return {"type": "keyword"}


MAPPINGS = {
    "dynamic": "strict",
    "_source": {
        # The boosted field is search-only; it duplicates displayed fields.
        "excludes": ["boosted", "speaker", "riding_search"],
    },
    "properties": {
        "id": _keyword(),
        "django_ct": _keyword(),
        "django_id": _keyword(),
        "doctype": _keyword(),
        "date": {"type": "date"},
        "url": _display_only(),

        # Who said/sponsored it
        "politician": _keyword(),
        "politician_id": _keyword(),
        "who_hocid": {"type": "long"},
        "party": _keyword(),
        "party_slug": _display_only(),
        "province": _keyword(),
        "riding": _display_only(),
        # Searchable at ordinary weight: a place name shouldn't make the MP
        # outrank everything, the way a name match should.
        "riding_search": _searchable_text('en'),
        "end_year": {"type": "integer", "index": False},

        # Where it was said
        "doc_url": _keyword(),
        "committee_slug": _keyword(),
        "committee_en": _display_only(),
        "committee_fr": _display_only(),
        "session": _keyword(),

        # Bills
        "number": {"type": "keyword", "normalizer": "lowercase"},
        # Normalized names a query might be exactly: a bill's short title, an
        # MP's name, a riding (see search.utils.title_key)
        "title_key": {"type": "keyword"},

        # Ranking signals for statements
        "procedural": {"type": "boolean"},
        "wordcount": {"type": "integer"},

        # Searchable text. `speaker` is the speaker's name, post and party;
        # `boosted` holds the strings that should dominate for a name-like
        # query: MP names, bill numbers and short titles.
        "text_en": _searchable_text('en', highlight=True),
        "text_fr": _searchable_text('fr', highlight=True),
        # Bills: their texts run from a page to a thousand, so here length
        # normalization is on, or an omnibus bill would out-score everything
        # on every term it happens to contain.
        "bill_text_en": _searchable_text('en', highlight=True, norms=True),
        "bill_text_fr": _searchable_text('fr', highlight=True, norms=True),
        "topic_en": _searchable_text('en'),
        "topic_fr": _searchable_text('fr'),
        "title_en": _searchable_text('en'),
        "title_fr": _searchable_text('fr'),
        "speaker": _searchable_text('en'),
        "boosted": _searchable_text('en'),
    },
}


def _write_index_pattern() -> str:
    return f"{get_alias_name()}-*"


def get_write_indices(client: Elasticsearch | None = None) -> list[str]:
    """All concrete indices behind the alias, including any being built.

    Incremental updates are written to every one of them, so an index being
    rebuilt in the background doesn't miss documents that change during the
    rebuild.
    """
    client = client or get_es_client()
    return sorted(client.indices.get(index=_write_index_pattern(), ignore_unavailable=True).keys())


def get_live_indices(client: Elasticsearch | None = None) -> list[str]:
    """Concrete indices the alias currently points to."""
    client = client or get_es_client()
    alias = get_alias_name()
    if not client.indices.exists_alias(name=alias):
        return []
    return sorted(client.indices.get_alias(name=alias).keys())


def new_index_name() -> str:
    return f"{get_alias_name()}-{datetime.datetime.now():%Y%m%d-%H%M%S}"


def create_index(name: str, client: Elasticsearch | None = None, bulk_load: bool = False) -> str:
    """Create a concrete index with our settings and mappings.

    With bulk_load=True, refreshes are disabled for faster initial loading;
    call finish_bulk_load() afterwards.
    """
    client = client or get_es_client()
    index_settings = {**INDEX_SETTINGS, "index": dict(INDEX_SETTINGS["index"])}
    if bulk_load:
        index_settings["index"]["refresh_interval"] = "-1"
    client.indices.create(index=name, settings=index_settings, mappings=MAPPINGS)
    logger.info("Created index %s", name)
    return name


def finish_bulk_load(name: str, client: Elasticsearch | None = None) -> None:
    client = client or get_es_client()
    client.indices.put_settings(index=name, settings={"index": {"refresh_interval": "1s"}})
    client.indices.refresh(index=name)


def swap_alias(new_index: str, client: Elasticsearch | None = None, delete_old: bool = True) -> list[str]:
    """Atomically point the alias at new_index. Returns the indices it replaced."""
    client = client or get_es_client()
    alias = get_alias_name()
    old_indices = [i for i in get_live_indices(client) if i != new_index]
    actions = [{"remove": {"index": i, "alias": alias}} for i in old_indices]
    actions.append({"add": {"index": new_index, "alias": alias}})
    client.indices.update_aliases(actions=actions)
    logger.info("Alias %s now points to %s (was %s)", alias, new_index, old_indices)
    if delete_old:
        for i in old_indices:
            client.indices.delete(index=i)
            logger.info("Deleted old index %s", i)
    return old_indices


class NoSearchIndexError(Exception):
    pass


def index_documents(docs, index: str | None = None, client: Elasticsearch | None = None) -> int:
    """Index prepared documents (as returned by index.get_search_dict).

    Writes to `index` if given, otherwise to every concrete index behind the
    alias. Returns the number of documents indexed.
    """
    client = client or get_es_client()
    docs = list(docs)
    if not docs:
        return 0
    targets = [index] if index else get_write_indices(client)
    if not targets:
        raise NoSearchIndexError(
            "No Elasticsearch index matches %s; run `manage.py rebuild_search_index`"
            % _write_index_pattern())
    for target in targets:
        actions = (
            {"_op_type": "index", "_index": target, "_id": doc['id'], "_source": doc}
            for doc in docs
        )
        try:
            helpers.bulk(client, actions, chunk_size=500, request_timeout=300)
        except helpers.BulkIndexError as e:
            # The library's message is only a count; say why Elasticsearch refused.
            raise helpers.BulkIndexError(
                f"{e.args[0]} into {target}: {_summarize_bulk_errors(e.errors)}", e.errors) from None
    return len(docs)


def _summarize_bulk_errors(errors: list[dict], limit: int = 3) -> str:
    """The distinct failure reasons in a BulkIndexError, most frequent first,
    e.g. "cluster_block_exception: index [x] blocked by: [TOO_MANY_REQUESTS/12/disk
    usage exceeded flood-stage watermark ...] (500 docs, e.g. hansards.statement.123)"."""
    by_reason: dict[str, list[str]] = {}
    for err in errors:
        item = next(iter(err.values()), {})
        detail = item.get('error', {})
        if isinstance(detail, dict):
            reason = f"{detail.get('type')}: {detail.get('reason')}"
            if detail.get('caused_by'):
                reason += f" (caused by {detail['caused_by'].get('type')}: {detail['caused_by'].get('reason')})"
        else:
            reason = str(detail)
        by_reason.setdefault(reason, []).append(str(item.get('_id')))
    ranked = sorted(by_reason.items(), key=lambda kv: -len(kv[1]))
    parts = [f"{reason} ({len(ids)} docs, e.g. {ids[0]})" for reason, ids in ranked[:limit]]
    if len(ranked) > limit:
        parts.append(f"and {len(ranked) - limit} other reason(s)")
    return "; ".join(parts)


def delete_documents(ids, client: Elasticsearch | None = None) -> None:
    client = client or get_es_client()
    ids = list(ids)
    if not ids:
        return
    for target in get_write_indices(client):
        actions = (
            {"_op_type": "delete", "_index": target, "_id": doc_id}
            for doc_id in ids
        )
        # A document that was never indexed is fine to "delete".
        helpers.bulk(client, actions, raise_on_error=False, request_timeout=120)
