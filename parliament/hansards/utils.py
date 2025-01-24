from collections.abc import Iterable
import itertools

from .models import Statement

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