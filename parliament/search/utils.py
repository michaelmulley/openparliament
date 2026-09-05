from collections import namedtuple
import math
import re
import urllib.request, urllib.parse, urllib.error

from django.utils.safestring import mark_safe

_FakePaginator = namedtuple('FakePaginator', 'num_pages count')

class SearchPaginator(object):
    """A dumb imitation of the Django Paginator."""

    def __init__(self, object_list, hits, pagenum, perpage):
        self.object_list = object_list
        self.hits = hits
        self.num_pages = int(math.ceil(float(self.hits) / float(perpage)))
        self.number = pagenum
        self.start_index = ((pagenum - 1) * perpage) + 1
        self.end_index = self.start_index + perpage - 1
        if self.end_index > self.hits:
            self.end_index = self.hits

    @property
    def paginator(self):
        return _FakePaginator(self.num_pages, self.hits)

    def has_previous(self):
        return self.number > 1

    def has_next(self):
        return self.number < self.num_pages

    def previous_page_number(self):
        return self.number - 1

    def next_page_number(self):
        return self.number + 1


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
                '%s: "%s"' % (key, self.filters[key])
                for key in sorted(self.filters.keys())
        )))
        return q.strip()


DATE_FILTER_RE = re.compile(
    r'^(?P<fy>\d{4})-(?P<fm>\d\d?)(?:-(?P<fd>\d\d?))?(?: to (?P<ty>\d{4})-(?P<tm>\d\d?)(?:-(?P<td>\d\d?))?)?')


def parse_date_filter(value):
    """Parses a Date filter ("2024-03", "2024-03-05", "2023-01 to 2024-06")
    into a (start, end) pair of dates, with end exclusive. Returns None if
    the value isn't understood."""
    from calendar import monthrange
    import datetime

    match = DATE_FILTER_RE.search(value)
    if not match:
        return None
    g = match.groupdict()
    try:
        start_date = datetime.date(int(g['fy']), int(g['fm']), int(g['fd']) if g['fd'] else 1)
        if g['ty']:
            if g['td']:
                end_date = datetime.date(int(g['ty']), int(g['tm']), int(g['td']))
            else:
                # Only YR-MO, find the last day of the month
                end_date = datetime.date(int(g['ty']), int(g['tm']),
                    monthrange(int(g['ty']), int(g['tm']))[1])
        elif g['fd']:
            # A full from date and no to date: search only that day
            end_date = start_date
        else:
            end_date = datetime.date(int(g['fy']), int(g['fm']),
                monthrange(int(g['fy']), int(g['fm']))[1])
    except ValueError:
        return None
    return start_date, end_date + datetime.timedelta(days=1)


def politician_result_html(party_short_name, party_slug, riding, end_year=None):
    """The one-line description shown for an MP in search results."""
    from django.utils.html import escape
    return '%s<span class="tag partytag_%s">%s</span> MP for %s%s' % (
        'was ' if end_year else '',
        escape(str(party_slug).lower()),
        escape(party_short_name),
        escape(riding),
        f' until {end_year}' if end_year else '',
    )


def title_key(text):
    """Normalizes a title (or a query) for exact whole-title matching:
    lowercase, accents folded, punctuation dropped."""
    import re
    import unicodedata
    if not text:
        return None
    # Punctuation (including em dashes) becomes a space before accents are
    # folded away, so "Rosemont—La Petite-Patrie" keeps its word boundaries.
    spaced = re.sub(r'[\W_]+', ' ', text)
    folded = unicodedata.normalize('NFKD', spaced).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', ' ', folded.lower()).strip() or None
