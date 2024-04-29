"""Search tools that interface with Solr."""

from calendar import monthrange
import datetime
import re

from django.conf import settings
from django.utils.html import escape
from django.utils.safestring import mark_safe

import pysolr

from parliament.core.utils import memoize_property
from parliament.search.utils import BaseSearchQuery

r_hl = re.compile(r'~(/?)hl~')
def autohighlight(results):
    """Puts in <em> for highlighted snippets."""
    if not hasattr(results, 'highlighting'):
        return results
    for doc in results.docs:
        for datefield in ('date', 'time'):
            if datefield in doc:
                doc[datefield] = datetime.datetime.strptime(
                    doc[datefield], "%Y-%m-%dT%H:%M:%SZ")
        if doc['id'] in results.highlighting:
            for (field, val) in list(results.highlighting[doc['id']].items()):
                if 'politician' not in doc['id']:
                    # GIANT HACK: in the current search schema, politician results are pre-escaped
                    val = escape(val[0])
                else:
                    val = val[0]
                if doc.get(field):
                    # If the text field is already there for the document, rename it full_text
                    doc['full_' + field] = doc[field]
                doc[field] = mark_safe(r_hl.sub(r'<\1em>', val))
    return results

solr = pysolr.Solr(settings.HAYSTACK_CONNECTIONS['default']['URL'])


class SearchQuery(BaseSearchQuery):
    """Converts a user search query into Solr's language, and
    gets the results from Solr."""

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
        'Type': 'type',
        'Document': 'doc_url'
    }

    DATE_FILTER_RE = re.compile(
        r'^(?P<fy>\d{4})-(?P<fm>\d\d?)(?:-(?P<fd>\d\d?))?(?: to (?P<ty>\d{4})-(?P<tm>\d\d?)(?:-(?P<td>\d\d?))?)?')

    def __init__(self, query, start=0, limit=15, user_params={},
            facet=False, full_text=False, solr_params={}):
        super(SearchQuery, self).__init__(query)
        self.start = start  # What offset to start from
        self.limit = limit  # How many results to return
        self.user_params = user_params  # request.GET, basically
        self.facet = facet  # Enable faceting?
        self.full_text = full_text
        self.extra_solr_params = solr_params

    def get_solr_query(self):
        searchparams = {
            'start': self.start,
            'rows': self.limit
        }
        if self.facet:
            searchparams['facet'] = 'true'
        if self.full_text:
            searchparams['fl'] = '*'

        solr_filters = []
        filter_types = set()

        for filter_name, filter_value in list(self.filters.items()):
            filter_name = self.ALLOWABLE_FILTERS[filter_name]

            if filter_name == 'date':
                match = self.DATE_FILTER_RE.search(filter_value)
                if not match:
                    continue
                g = match.groupdict()
                start_date = datetime.date(int(g['fy']), int(g['fm']), int(g['fd']) if g['fd'] else 1)
                if g['ty']:
                    if g['td']:
                        # If we have a full date, use it
                        end_date = datetime.date(int(g['ty']), int(g['tm']), int(g['td']))
                    else:
                        # Otherwise, just YR-MO, find the last day of the month
                        end_date = datetime.date(int(g['ty']), int(g['tm']),
                            monthrange(int(g['ty']), int(g['tm']))[1])
                else:
                    # We don't have a TO date
                    if g['fd']:
                        # We have a full from date, search only that day
                        end_date = start_date
                    else:
                        # Only YR-MO, find the last day of the month
                        end_date = datetime.date(int(g['fy']), int(g['fm']),
                            monthrange(int(g['fy']), int(g['fm']))[1])
                end_date += datetime.timedelta(days=1)
                filter_value = '[%sT00:00:00.000Z TO %sT00:01:01.000Z]' % (start_date, end_date)

            elif filter_name == 'type':
                filter_name = 'doctype'

            if ' ' in filter_value and filter_name != 'date':
                filter_value = '"%s"' % filter_value

            filter_value = filter_value.replace('/', r'\/')

            if filter_name in ['who_hocid', 'politician_id', 'politician']:
                filter_tag = 'fperson'
            elif filter_name == 'doc_url':
                filter_tag = 'fdate'
            else:
                filter_tag = 'f' + filter_name

            filter_types.add(filter_name)
            solr_filters.append('{!tag=%s}%s:%s' % (filter_tag, filter_name, filter_value))

        if solr_filters and not self.bare_query:
            solr_query = '*:*'
        else:
            solr_query = self.bare_query

        if solr_filters:
            searchparams['fq'] = solr_filters

        self.committees_only = 'Committee' in self.filters or self.filters.get('Type') == 'committee'
        self.committees_maybe = 'Type' not in self.filters or self.committees_only

        if self.facet:
            if self.committees_only:
                searchparams['facet.range.start'] = '2006-01-01T00:00:00.000Z'
            else:
                searchparams['facet.range.start'] = '1994-01-01T00:00:00.000Z'

        searchparams.update(self.validated_user_params)
        searchparams.update(self.extra_solr_params)

        # Our version of pysolr doesn't like Unicode
        if searchparams.get('fq'):
            searchparams['fq'] = [f.encode('utf-8') for f in searchparams['fq']]

        return (solr_query, searchparams)

    @property
    @memoize_property
    def validated_user_params(self):
        p = {}
        for opt in self.ALLOWABLE_OPTIONS:
            if opt in self.user_params and self.user_params[opt] in self.ALLOWABLE_OPTIONS[opt]:
                p[opt] = self.user_params[opt]
        return p

    @property
    def solr_results(self):
        if not getattr(self, '_results', None):
            bare_query, searchparams = self.get_solr_query()
            self._results = autohighlight(solr.search(bare_query, **searchparams))
        return self._results

    @property
    def hits(self):
        return self.solr_results.hits

    @property
    def facet_fields(self):
        return self.solr_results.facets.get('facet_fields')

    @property
    def documents(self):
        return self.solr_results.docs

    @property
    @memoize_property
    def date_counts(self):
        counts = []
        if self.facet and 'facet_ranges' in self.solr_results.facets:
            datefacets = self.solr_results.facets['facet_ranges']['date']['counts']
            counts = [
                (int(datefacets[i][:4]), datefacets[i+1])
                for i in range(0, len(datefacets), 2)
            ]

            if self.committees_only:
                # If we're searching only committees, we by definition won't have
                # results before 1994, so let's take them off of the graph.
                counts = [c for c in counts if c[0] >= 2006]
        return counts

    @property
    def discontinuity(self):
        if self.solr_results and self.committees_maybe and not self.committees_only:
            return 2006
        return None
