import json
import re
import sys
import time
from pathlib import Path

from django.core.management.base import BaseCommand

from parliament.search.es import SearchQuery

DEFAULT_QUERIES = Path(__file__).resolve().parents[2] / 'eval_queries.txt'
r_tags = re.compile(r'<[^>]+>')


def load_queries(path):
    queries, category = [], ''
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith('#'):
            category = line.lstrip('# ').strip()
            continue
        queries.append((category, line))
    return queries


def summarize(doc):
    date = doc['date'].strftime('%Y-%m-%d') if doc.get('date') else '----------'
    snippet = r_tags.sub('', str(doc.get('text', ''))).replace('\n', ' ')
    return {
        'url': doc['url'], 'doctype': doc['doctype'], 'date': date,
        'politician': doc.get('politician', ''), 'snippet': snippet[:110],
    }


class Command(BaseCommand):
    help = """Runs the evaluation queries (parliament/search/eval_queries.txt) and prints
the top results for each, for eyeballing ranking changes. --json writes a
machine-readable dump to stdout (human output goes to stderr); --compare
reports how much the top results moved against an earlier dump."""

    def add_arguments(self, parser):
        parser.add_argument('--queries', default=str(DEFAULT_QUERIES))
        parser.add_argument('--top', type=int, default=6)
        parser.add_argument('--json', action='store_true')
        parser.add_argument('--compare', help="Earlier --json dump to compare against")
        parser.add_argument('--only', help="Substring: run only queries containing this")

    def handle(self, **options):
        out_stream = sys.stderr if options['json'] else self.stdout

        class _Out:
            def write(self, text):
                out_stream.write(text.rstrip('\n') + '\n')
        out = _Out()
        queries = load_queries(options['queries'])
        if options['only']:
            queries = [q for q in queries if options['only'].lower() in q[1].lower()]
        previous = json.load(open(options['compare'])) if options['compare'] else {}

        results = {}
        zero, total_ms, moved = 0, 0, []
        for category, query in queries:
            sq = SearchQuery(query, facet=False)
            t = time.time()
            docs = sq.documents
            ms = (time.time() - t) * 1000
            total_ms += ms
            top = [summarize(d) for d in docs[:options['top']]]
            results[query] = {'category': category, 'hits': sq.hits, 'ms': round(ms),
                              'suggestion': getattr(sq, 'suggestion', None), 'top': top}
            if not sq.hits:
                zero += 1

            out.write(f"\n### [{category}] {query}  ->  {sq.hits} hits, {ms:.0f}ms")
            if results[query]['suggestion']:
                out.write(f"    did you mean: {results[query]['suggestion']}")
            for d in top:
                out.write(f"  [{d['doctype']:9}] {d['date']} {d['politician'][:22]:22} {d['url'][:44]:44} | {d['snippet'][:80]}")
            if query in previous:
                old = [d['url'] for d in previous[query]['top']]
                new = [d['url'] for d in top]
                same_first = bool(old) and bool(new) and old[0] == new[0]
                overlap = len(set(old) & set(new))
                if not same_first or overlap < len(new):
                    moved.append((query, same_first, overlap, len(new), previous[query]['hits'], sq.hits))
                    out.write(f"  ~ changed: first {'same' if same_first else 'DIFFERENT'}, "
                              f"{overlap}/{len(new)} overlap, hits {previous[query]['hits']} -> {sq.hits}")

        out.write(f"\n{len(queries)} queries, {zero} with no results, mean {total_ms / max(len(queries), 1):.0f}ms")
        if previous:
            out.write(f"{len(moved)} of {len(queries)} queries changed vs {options['compare']}")
        if options['json']:
            self.stdout.write(json.dumps(results, indent=1, ensure_ascii=False))
