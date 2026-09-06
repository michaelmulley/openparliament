"""Matching newly indexed items against saved searches (alert topics).

Called by consume_indexing_queue with the identifiers it just indexed. Each
active topic's search is run restricted to those identifiers, and every hit
becomes a TopicMatch, once; send_email_alerts mails them out.
"""

import collections
import datetime
import itertools
import logging

from parliament.alerts.models import Topic, TopicMatch
from parliament.hansards.models import OldSlugMapping, Statement
from parliament.search.es_index import get_alias_name, get_es_client

logger = logging.getLogger(__name__)

# Only these can trigger alerts (MPs' pages change all the time, silently)
ALERTABLE_PREFIXES = ('hansards.statement.', 'bills.bill.')
# Items dated longer ago than this never alert, however recently indexed:
# a re-imported old sitting isn't news. Late-published committee evidence is.
ALERT_MAX_AGE_DAYS = 90

IDS_PER_SEARCH = 500
TOPICS_PER_MSEARCH = 100


class MatchingError(Exception):
    """Some searches failed in a way a retry might fix. The caller should
    keep its indexing tasks so the batch is matched again next time (recording
    a match twice is harmless)."""


def _is_retryable(status) -> bool:
    return status is None or status >= 500 or status == 429


def _parse_date(value):
    return datetime.datetime.fromisoformat(value.replace('Z', ''))


def _prior_urls(matches) -> dict[str, list[str]]:
    """For matched statements whose slug a re-import has changed, the URLs
    they had before (most recent first), from OldSlugMapping."""
    url_by_pk = {}
    for match in matches:
        if match.item_id.startswith('hansards.statement.'):
            url_by_pk.setdefault(int(match.item_id.rsplit('.', 1)[1]), match.url)
    if not url_by_pk:
        return {}
    rows = list(Statement.objects.filter(id__in=url_by_pk).values_list('id', 'document_id', 'slug'))
    mappings = collections.defaultdict(dict)  # document_id -> {new_slug: old_slug}
    for document_id, old_slug, new_slug in OldSlugMapping.objects.filter(
            document_id__in={r[1] for r in rows}).values_list('document_id', 'old_slug', 'new_slug'):
        mappings[document_id][new_slug] = old_slug
    prior = {}
    for pk, document_id, slug in rows:
        url = url_by_pk[pk]
        if not slug or not url.endswith('/' + slug + '/') or document_id not in mappings:
            continue
        base = url[:-len(slug) - 1]
        earlier, s = [], slug
        while s in mappings[document_id] and len(earlier) < 10:
            s = mappings[document_id][s]
            if base + s + '/' in earlier:
                break
            earlier.append(base + s + '/')
        if earlier:
            prior[url] = earlier
    return prior


def _carry_forward(matches) -> list:
    """Where a matched statement is one whose slug a re-import changed, and
    the topic already has a match under the old URL, moves that record to
    the new URL (keeping whether it was sent) instead of matching afresh.
    Returns the matches still to be recorded."""
    prior = _prior_urls(matches)
    if not prior:
        return matches
    topic_ids = {m.topic_id for m in matches}
    existing = {(m.topic_id, m.url): m for m in TopicMatch.objects.filter(
        topic_id__in=topic_ids, url__in={u for urls in prior.values() for u in urls})}
    if not existing:
        return matches
    already_current = set(TopicMatch.objects.filter(
        topic_id__in=topic_ids, url__in=prior).values_list('topic_id', 'url'))
    kept = []
    for match in matches:
        old = next((existing[(match.topic_id, u)] for u in prior.get(match.url, ())
                    if (match.topic_id, u) in existing), None)
        if old is None:
            kept.append(match)
        elif (match.topic_id, match.url) not in already_current:
            old.url, old.item_id, old.date = match.url, match.item_id, match.date
            old.save(update_fields=['url', 'item_id', 'date'])
    return kept


def record_matches(identifiers, now=None) -> int:
    """Records a TopicMatch for every active topic that each of the given
    just-indexed items matches. Returns the number of matches found. An item
    (by URL) already matched to a topic is not recorded again, but its
    search identifier is brought up to date, since a re-imported statement
    gets a new one."""
    ids = sorted({i for i in identifiers if i.startswith(ALERTABLE_PREFIXES)})
    if not ids:
        return 0
    topics = list(Topic.objects.active())
    if not topics:
        return 0

    now = now or datetime.datetime.now()
    date_filter = '%s to %s' % ((now - datetime.timedelta(days=ALERT_MAX_AGE_DAYS)).strftime('%Y-%m-%d'),
                                now.strftime('%Y-%m-%d'))
    client = get_es_client()
    alias = get_alias_name()
    client.indices.refresh(index=alias)  # the items were indexed a moment ago

    found = 0
    retryable_errors = []
    for id_chunk in itertools.batched(ids, IDS_PER_SEARCH):
        for topic_chunk in itertools.batched(topics, TOPICS_PER_MSEARCH):
            searches = []
            for topic in topic_chunk:
                query = topic.search_query(id_chunk)
                query.filters['Date'] = date_filter
                body = query.get_search_body()
                body['_source'] = ['url', 'date']
                body.pop('highlight', None)
                searches += [{'index': alias}, body]
            responses = client.msearch(searches=searches)['responses']

            matches = []
            for topic, response in zip(topic_chunk, responses):
                if 'error' in response:
                    error = response['error']
                    if _is_retryable(response.get('status')):
                        retryable_errors.append((topic.query, error))
                    else:
                        # This query itself is the problem; retrying won't help
                        logger.error("Alert matching failed for topic %r: %s", topic.query, error)
                    continue
                for hit in response['hits']['hits']:
                    matches.append(TopicMatch(
                        topic=topic, item_id=hit['_id'], url=hit['_source']['url'],
                        date=_parse_date(hit['_source']['date']), created=now))
            matches = _carry_forward(matches)
            if matches:
                TopicMatch.objects.bulk_create(
                    matches, update_conflicts=True, unique_fields=['topic', 'url'],
                    update_fields=['item_id', 'date'])
                Topic.objects.filter(id__in={m.topic_id for m in matches}).update(last_found=now)
                found += len(matches)
    if retryable_errors:
        raise MatchingError("%d alert searches failed (first: %r: %s)" % (
            len(retryable_errors), retryable_errors[0][0], retryable_errors[0][1]))
    return found
