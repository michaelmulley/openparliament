from collections.abc import Iterable
import itertools
import json

from django.conf import settings

from .models import Statement, Document
from parliament.summaries.models import Summary

def get_major_speeches(statements: Iterable[Statement], min_words=500) -> list[Statement]:
    """
    Returns speeches over a given wordcount; the extra logic is to account for long speeches
    that are interrupted by the Speaker but then resume.
    """
    current = []
    all = []
    for s in statements:
        if s.procedural or 'Speaker' in s.who_en:
            continue
        if current and s.member_id == current[0].member_id:
            if (s.sequence - current[-1].sequence) in (1,2,3):
                current.append(s)
                continue
        if current and sum(c.wordcount for c in current) > min_words:
            all.extend(current)
        current = [s]
    return all

def group_by_party(statements: Iterable[Statement]) -> dict[str, list[Statement]]:
    st = sorted(statements, key=lambda s: (s.member.party_id if s.member else 0, s.time, s.sequence))
    grouped_statements = itertools.groupby(st, key=lambda s: s.member.party.short_name if s.member else '')
    return {party: list(group) for party, group in grouped_statements}

class HansardSection:

    def __init__(self, s):
        self.statements = [s]
        self.other_segments = []
        self.segment_minutes = []

    def add_statement(self, s):
        self.statements.append(s)

    def combine_with(self, other):
        # We've found what appears to be another segment of the same debate, keep them together.
        if ((other.statements[0]['sequence'] - self.statements[-1]['sequence']) > 5
                    and other.statements[0]['time'] != self.statements[-1]['time']):
            # The segements aren't super close together, label them as separate
            self.other_segments.append(other.slug)
        if not self.segment_minutes:
            self.segment_minutes = [self.minutes]
        self.segment_minutes.append(other.minutes)
        self.statements.extend(other.statements)

    @property
    def h1(self):
        return self.statements[0]['h1_en']

    @property
    def h2(self):
        return self.statements[0]['h2_en']
    
    @property
    def h3(self):
        return self.statements[0]['h3_en']

    @property
    def slug(self):
        return self.statements[0]['slug']
    
    @property
    def all_slugs(self):
        return [s['slug'] for s in self.statements]
    
    @property
    def bill_debated(self):
        return self.statements[0]['bill_debated__number']
    
    @property
    def bill_debate_stage(self):
        return self.statements[0]['bill_debate_stage']
    
    @property
    def combine_key(self):
        if self.bill_debated:
            return (self.bill_debated, self.bill_debate_stage)
        return (self.h1.lower(), self.h2.lower(), self.h3.lower())
    
    @property
    def num_segments(self):
        return len(self.other_segments) + 1

    @property
    def wordcount(self):
        return sum(s['wordcount'] for s in self.statements if not s['procedural'])

    @property
    def minutes(self):
        if self.segment_minutes:
            return sum(self.segment_minutes)
        return int((self.statements[-1]['time'] - self.statements[0]['time']).seconds / 60)
    
    @property
    def should_include(self):
        return self.bill_debate_stage == '1' or self.wordcount >= 500 or max(s['wordcount'] for s in self.statements) >= 300
    
    def get_statements(self, doc):
        return doc.statement_set.filter(slug__in=[s['slug'] for s in self.statements])

    @property
    def display_heading(self):
        if self.h1.lower() in ('oral questions', 'oral question period'):
            return 'Question Period'
        if self.h1.lower() == 'adjournment proceedings':
            return 'Adjournment Debates'
        if self.h1.lower() == 'statements by members':
            return 'Statements by Members' # the capitalization is inconsistent in Hansard
        if self.bill_debated:
            return self.h2
        for heading in ('h3_en', 'h2_en', 'h1_en'):
            last = self.statements[0][heading].lower()
            for s in self.statements:
                if not s[heading] or s[heading].lower() != last:
                    break
            else:
                return self.statements[0][heading]

    @property
    def subheds(self):
        if self.h1.lower() in ('oral questions', 'oral question period', 'statements by members', 'adjournment proceedings'):
            heading = 'h2_en'
        elif self.h2 == 'Petitions':
            heading = 'h3_en'
        else:
            return []
        r = {}
        for s in self.statements:
            if s[heading] and s[heading] not in r:
                r[s[heading]] = s['slug']
        return list(r.items())
    
    def to_json(self):
        return dict((k, getattr(self, k)) for k in ('other_segments', 'slug', 'all_slugs', 
                                                    'bill_debated', 'bill_debate_stage', 'wordcount', 'minutes',
                                                    'display_heading', 'subheds'))

    def __repr__(self):
        return f"{self.display_heading} ** {self.h1} -- {self.h2} -- {self.h3 + " -- " if self.h3 else ''}{self.wordcount} words, n={len(self.statements)} {self.bill_debated}"
    

def get_hansard_sections(doc) -> list[dict]:
    """Given a Hansard Document, returns a list of dicts, each representing a section of the Hansard.
    
    Keys are:
    - slug: slug of the first statement in the section; can be used to make a link
    - all_slugs: list of all slugs for statements in the section
    - bill_debated: number (e.g. "C-27") of the bill being debated in this section, if applicable
    - bill_debate_stage: what stage of bill debate does this section represent; see bill_debate_stage column on Statement
    - wordcount: total words, an integer
    - minutes: roughly how many minutes of debate the section represents
    - display_heading: a string, how to identify this section in the UI
    - subheds: some sections are organized with a list of subheadings. a list of ("heading_name", "slug_to_link_to") tuples.
    - other_segments: if the debate was interrupted and then resumed, a list of slugs to link to for the additional segments
        of the debate
    """
    r = {}
    current = None

    statements = doc.statement_set.values('h1_en', 'h2_en', 'h3_en', 'slug', 'wordcount', 'time', 'bill_debated__number', 'bill_debate_stage', 'procedural', 'sequence')

    def _save_current():
        if current and current.wordcount:
            if current.combine_key in r:
                r[current.combine_key].combine_with(current)
            else:
                r[current.combine_key] = current
    
    for s in statements:
        if current is None:
            current = HansardSection(s)
            continue

        if s['h2_en'].lower().startswith('questions '):
            continue

        if (s['h1_en'] == current.h1 and s['h2_en'] == current.h2
                and s['h3_en'] == current.h3 and s['bill_debated__number'] == current.bill_debated):
            current.add_statement(s)
        elif s['h1_en'] == current.h1 and s['h1_en'].lower() in ('oral questions', 'oral question period', 'statements by members', 'adjournment proceedings'):
            current.add_statement(s)
        elif s['h1_en'] == current.h1 and s['h2_en'] == current.h2 and s['h2_en'] in ('Petitions'):
            current.add_statement(s)
        else:
            _save_current()
            current = HansardSection(s)
    _save_current()
    return [s.to_json() for s in r.values() if s.should_include]

def get_hansard_sections_or_summary(document: Document) -> tuple[list[dict], Summary | None]:
    """Returns the summary structure and either a Summary object (if it's a saved LLM summary) or None, if it isn't."""
    try:
        summary = Summary.objects.get(summary_type='hansard_topics', identifier=document.get_absolute_url(),
                                      public=True)
        if not summary.summary_json:
            raise Summary.DoesNotExist(f"No summary JSON for {summary}")
        return summary.summary_json, summary
    except Summary.DoesNotExist:
        return get_hansard_sections(document), None