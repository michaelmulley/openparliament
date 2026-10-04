from collections import defaultdict
from itertools import groupby
import json
from pathlib import Path
import random
import re

from django.core.management.base import BaseCommand

from parliament.bills.models import Bill
from parliament.hansards.models import Document
from parliament.hansards.utils import get_hansard_sections, get_major_speeches, group_by_party
from parliament.summaries.checks import munge_urls
from parliament.summaries.generation.hansard_topics import section_task
from parliament.summaries.generation.utils import get_transcript
from parliament.summaries.models import Summary
from parliament.summaries.prompts import TASKS

DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / 'eval' / 'evalset.json'

# Which model tier (llms.QUICK or llms.THINKING) production uses for each task
TIERS = {
    'bill_overview': 'quick',
    'bill_party': 'thinking',
    'section': 'quick',
    'adjournment': 'quick',
    'qp': 'thinking',
    'subheds': 'quick',
}


def _size(wordcount, *cutoffs):
    for c in cutoffs:
        if wordcount < c:
            return f'<{c}'
    return f'>={cutoffs[-1]}'


class Command(BaseCommand):
    help = """Exports a fixed set of summary LLM calls (the inputs our prompts are built from,
plus transcripts) for the promptfoo evals in parliament/summaries/eval/. Cases are
spread across the branches in the prompt logic (sizes, bill vs non-bill, etc.) and
include the summary currently on the site for reference."""

    def add_arguments(self, parser):
        parser.add_argument('--output', default=str(DEFAULT_OUTPUT))
        parser.add_argument('--per-task', type=int, default=8,
                            help="Cases per kind of LLM call")
        parser.add_argument('--hansards', type=int, default=30,
                            help="Draw Hansard cases from this many recent sittings")
        parser.add_argument('--bill-summaries', type=int, default=20,
                            help="Draw bill-debate cases from this many recent bill summaries")
        parser.add_argument('--seed', type=int, default=1)

    def handle(self, **options):
        self.rng = random.Random(options['seed'])
        candidates = defaultdict(list)
        self.hansard_candidates(candidates, options['hansards'])
        self.bill_candidates(candidates, options['bill_summaries'])

        cases = []
        for task in TASKS:
            picked = self.pick(candidates[task], options['per_task'])
            for c in picked:
                cases.append(self.build_case(task, c))
            self.stderr.write(f"{task}: {len(picked)} cases (of {len(candidates[task])} candidates)")

        Path(options['output']).write_text(json.dumps(cases, indent=1, ensure_ascii=False))
        self.stderr.write(f"Wrote {len(cases)} cases to {options['output']}")

    def pick(self, cands: list[dict], n: int) -> list[dict]:
        """Picks n candidates, round-robin across buckets so each branch of the prompt logic
        is represented."""
        buckets = defaultdict(list)
        for c in cands:
            buckets[c['bucket']].append(c)
        for b in buckets.values():
            self.rng.shuffle(b)
        order = sorted(buckets)
        picked = []
        while len(picked) < n and any(buckets.values()):
            for b in order:
                if buckets[b] and len(picked) < n:
                    picked.append(buckets[b].pop())
        return picked

    def build_case(self, task: str, c: dict) -> dict:
        build, _ = TASKS[task]
        prompt = build(**c['prompt_args'])
        statements = c['get_statements']()
        transcript = get_transcript(statements, para_urls=prompt.para_urls)
        if prompt.munge_urls:
            transcript, _ = munge_urls(transcript, rng=random.Random(c['id']))
        return {
            'id': c['id'],
            'task': task,
            'tier': TIERS[task],
            'label': c['label'],
            'source_url': c['source_url'],
            'bucket': ' · '.join(map(str, c['bucket'])) if isinstance(c['bucket'], tuple) else str(c['bucket']),
            'prompt_args': c['prompt_args'],
            'parse_args': c.get('parse_args', {}),
            'transcript': transcript,
            'current_output': c.get('current_output'),
        }

    def hansard_candidates(self, candidates, n_docs):
        docs = Document.debates.filter(public=True).order_by('-date')[:n_docs]
        for doc in docs:
            doc_url = doc.get_absolute_url()
            try:
                stored = Summary.objects.get(summary_type='hansard_topics', identifier=doc_url).summary_json
            except Summary.DoesNotExist:
                stored = []
            stored_by_slug = {s['slug']: s for s in stored}
            for section in get_hansard_sections(doc):
                task = section_task(section)
                if task is None:
                    continue
                current = stored_by_slug.get(section['slug'], {})
                label = f"{doc.date} · {section['display_heading']}"
                source_url = doc_url + section['slug'] + '/'
                slugs = section['all_slugs']
                statements = lambda doc=doc, slugs=slugs: list(doc.statement_set.filter(slug__in=slugs))
                base = dict(label=label, source_url=source_url)

                if task == 'section':
                    candidates[task].append(dict(base,
                        id=f"section {doc.date} {section['slug']}",
                        bucket=(_size(section['wordcount'], 1500, 2000, 15000), bool(section['bill_debated'])),
                        prompt_args=dict(wordcount=section['wordcount'], bill_debated=bool(section['bill_debated'])),
                        get_statements=statements,
                        current_output=current.get('summary_text')))

                elif task == 'subheds':
                    section_type = 'petition' if section['display_heading'].startswith('Petition') else 'statement'
                    candidates[task].append(dict(base,
                        id=f"subheds {doc.date} {section['slug']}",
                        bucket=section_type,
                        prompt_args=dict(section_type=section_type),
                        get_statements=statements,
                        current_output=current.get('subheds')))

                elif task == 'qp':
                    # Mirrors _summarize_qp
                    parties = {}
                    for s in doc.statement_set.filter(slug__in=slugs).select_related('member__party'):
                        if s.member:
                            parties.setdefault(s.member.party.short_name, []).append(s)
                    party_names = [p for p in parties if p != 'Independent']
                    stored_chunks = current.get('summary_chunks') or []
                    for i, party_name in enumerate(party_names):
                        party_wordcount = sum(s.wordcount for s in parties[party_name] if not s.procedural)
                        candidates[task].append(dict(base,
                            id=f"qp {doc.date} {party_name}",
                            label=f"{label} · {party_name}",
                            bucket=(_size(party_wordcount, 200, 1500), i > 0),
                            # The summaries already written for earlier parties come from the one on the site
                            prompt_args=dict(party_wordcount=party_wordcount,
                                             prior_summaries=stored_chunks[:i] if len(stored_chunks) == len(party_names) else []),
                            get_statements=lambda s=parties[party_name]: s,
                            current_output=stored_chunks[i] if len(stored_chunks) == len(party_names) else None))

                elif task == 'adjournment':
                    # Mirrors _summarize_adjournment
                    stored_chunks = current.get('summary_chunks') or []
                    all_statements = list(doc.statement_set.filter(slug__in=slugs))
                    for h2, chunk in groupby(all_statements, lambda s: s.h2_en):
                        chunk = list(chunk)
                        wordcount = sum(s.wordcount for s in chunk if not s.procedural)
                        if wordcount < 300:
                            continue
                        current_output = next((c for c in stored_chunks if f"({chunk[0].urlcache})" in c),
                                              current.get('summary_text'))
                        candidates[task].append(dict(
                            id=f"adjournment {doc.date} {chunk[0].slug}",
                            label=f"{label} · {h2}",
                            source_url=chunk[0].urlcache,
                            bucket=_size(wordcount, 1000),
                            prompt_args={},
                            get_statements=lambda chunk=chunk: chunk,
                            current_output=current_output))

    def bill_candidates(self, candidates, n_summaries):
        summaries = Summary.objects.filter(
            summary_type__in=['stage_2', 'stage_3', 'stage_report']).order_by('-created')[:n_summaries]
        for summary in summaries:
            _, _, session_id, number, _ = summary.identifier.split('/')
            bill = Bill.objects.get(session_id=session_id, number=number)
            stage = summary.summary_type.removeprefix('stage_')
            # Mirrors create_reading_summary
            statements = list(bill.get_debate_at_stage(stage).select_related('member', 'member__party'))
            major_speeches = get_major_speeches(statements)
            if not major_speeches:
                continue
            parts = [p.strip() for p in re.split(r'\n\s*\n', summary.summary_text)]
            label = f"{bill.number} {summary.get_summary_type_display()}"
            base = dict(label=label, source_url=summary.identifier)

            candidates['bill_overview'].append(dict(base,
                id=f"bill_overview {session_id} {bill.number} {stage}",
                bucket=stage,
                prompt_args={},
                get_statements=lambda s=major_speeches: s,
                current_output=parts[0]))

            for party_name, party_speeches in group_by_party(major_speeches).items():
                current = next((f"{p}\n\n{parts[i+1]}" for i, p in enumerate(parts[:-1])
                                if p == f"**{party_name}**"), None)
                candidates['bill_party'].append(dict(base,
                    id=f"bill_party {session_id} {bill.number} {stage} {party_name}",
                    label=f"{label} · {party_name}",
                    bucket=(party_name, _size(sum(s.wordcount for s in party_speeches), 5000)),
                    prompt_args={},
                    parse_args=dict(party_name=party_name),
                    get_statements=lambda s=party_speeches: s,
                    current_output=current))
