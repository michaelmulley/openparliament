"""Search tools that interface with Solr."""

import datetime
import re

from django.conf import settings
from django.utils.html import escape
from django.utils.safestring import mark_safe

import pysolr

from parliament.core.utils import memoize_property

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
            for (field, val) in results.highlighting[doc['id']].items():
                if 'politician' not in doc['id']:
                    # GIANT HACK: in the current search schema, politician results are pre-escaped
                    val = escape(val[0])
                else:
                    val = val[0]
                doc[field] = mark_safe(r_hl.sub(r'<\1em>', val))
    return results

solr = pysolr.Solr(settings.HAYSTACK_SOLR_URL)


class SearchQuery(object):
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
        'Type': 'type'
    }

    def __init__(self, query, start=0, limit=15, user_params={}, facet=False):
        self.raw_query = query  # The query, as entered by the user
        self.start = start  # What offset to start from
        self.limit = limit  # How many results to return
        self.user_params = user_params  # request.GET, basically
        self.facet = facet  # Enable faceting?

    def get_solr_query(self):
        searchparams = {
            'start': self.start,
            'rows': self.limit
        }
        if self.facet:
            searchparams['facet'] = 'true'

        # Extract filters from query
        filters = []
        filter_types = set()

        def extract_filter(match):
            filter_name = self.ALLOWABLE_FILTERS[match.group(1)]
            filter_value = match.group(2)

            if filter_name == 'date':
                match = re.search(r'^(\d{4})-(\d\d?) to (\d{4})-(\d\d?)', filter_value)
                if not match:
                    return ''
                (fromyear, frommonth, toyear, tomonth) = [int(x) for x in match.groups()]
                tomonth += 1
                if tomonth == 13:
                    tomonth = 1
                    toyear += 1
                filter_value = '[{0:02}-{1:02}-01T00:01:01.000Z TO {2:02}-{3:02}-01T00:01:01.000Z]'.format(fromyear, frommonth, toyear, tomonth)

            elif filter_name == 'type':
                filter_name = 'django_ct'
                if filter_value == 'debate':
                    filter_value = 'hansards.statement'
                    filters.append('committee_slug:""')
                elif filter_value == 'committee':
                    filter_value = 'hansards.statement'
                    filters.append('-committee_slug:""')
                elif filter_value == 'bill':
                    filter_value = 'bills.bill'

            if ' ' in filter_value and filter_name != 'date':
                filter_value = u'"%s"' % filter_value

            if filter_name in ['who_hocid', 'politician_id', 'politician']:
                filter_tag = 'fperson'
            else:
                filter_tag = 'f' + filter_name

            filter_types.add(filter_name)
            filters.append(u'{!tag=%s}%s:%s' % (filter_tag, filter_name, filter_value))
            return ''
        bare_query = re.sub(r'(%s): "([^"]+)"' % '|'.join(self.ALLOWABLE_FILTERS),
            extract_filter, self.raw_query)
        bare_query = re.sub(r'\s\s+', ' ', bare_query).strip()
        if filters and not bare_query:
            bare_query = '*:*'

        if filters:
            searchparams['fq'] = filters

        self.committees_only = 'committee_slug' in filter_types or '-committee_slug:""' in filters
        self.committees_maybe = 'django_ct' not in filter_types or self.committees_only

        if self.facet:
            if self.committees_only:
                searchparams['facet.range.start'] = '2006-01-01T00:00:00.000Z'
            else:
                searchparams['facet.range.start'] = '1994-01-01T00:00:00.000Z'

        searchparams.update(self.validated_user_params)

        # Our version of pysolr doesn't like Unicode
        if searchparams.get('fq'):
            searchparams['fq'] = map(lambda f: f.encode('utf-8'), searchparams['fq'])

        return (bare_query, searchparams)

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
                counts = filter(lambda c: c[0] >= 2006, counts)
        return counts

    @property
    def discontinuity(self):
        if self.solr_results and self.committees_maybe and not self.committees_only:
            return 2006
        return None
