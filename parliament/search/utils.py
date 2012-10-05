import math
import re
import urllib

from django.utils.safestring import mark_safe


class SearchPaginator(object):
    """A dumb imitation of the Django Paginator."""

    def __init__(self, object_list, hits, pagenum, perpage,
            params, allowable_fields=None):
        self.object_list = object_list
        if pagenum > 1:
            self.has_previous = True
            self.previous_page_number = pagenum - 1
        else:
            self.has_previous = False
        self.hits = hits
        self.num_pages = int(math.ceil(float(self.hits) / float(perpage)))
        if pagenum < self.num_pages:
            self.has_next = True
            self.next_page_number = pagenum + 1
        self.number = pagenum
        self.start_index = ((pagenum - 1) * perpage) + 1
        self.end_index = self.start_index + perpage - 1
        if self.end_index > self.hits:
            self.end_index = self.hits

        if allowable_fields:
            good_params = dict([(k.encode('utf8'), v.encode('utf8')) for (k, v) in params.items() if k in allowable_fields])
        else:
            good_params = dict([(k.encode('utf8'), v.encode('utf8')) for (k, v) in params.items() if k not in ('page', 'partial')])
        self.querystring = mark_safe(urllib.urlencode(good_params))

    @property
    def paginator(self):
        return {'num_pages': self.num_pages, 'count': self.hits}


class BaseSearchQuery(object):

    ALLOWABLE_FILTERS = {}

    def __init__(self, query):
        self.raw_query = query
        self.filters = {}

        def extract_filter(match):
            self.filters[match.group(1)] = match.group(2)
            return ''

        self.bare_query = re.sub(r'(%s): "([^"]+)"' % '|'.join(self.ALLOWABLE_FILTERS),
            extract_filter, self.raw_query)
        self.bare_query = re.sub(r'\s\s+', ' ', self.bare_query).strip()

    @property
    def normalized_query(self):
        q = (self.bare_query
            + (' ' if self.bare_query and self.filters else '')
            + ' '.join((
                u'%s: "%s"' % (key, self.filters[key])
                for key in sorted(self.filters.keys())
        )))
        return q.strip()
