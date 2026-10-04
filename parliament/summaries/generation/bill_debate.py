import json
import logging
from typing import Literal

from django.db.models import Sum, Max, Count

from parliament.hansards.models import Statement
from parliament.hansards.utils import get_major_speeches, group_by_party
from parliament.bills.models import Bill
from parliament.summaries.llm import LLMProviderError, llms
from parliament.summaries.models import Summary
from parliament.summaries.prompts import (bill_overview_prompt, parse_bill_overview,
                                          bill_party_prompt, parse_bill_party)

from .utils import LinkError, get_transcript, call_llm, retry, save_summary

logger = logging.getLogger(__name__)

def create_reading_summary(bill: Bill, reading: Literal['2','3','report'], model: str | None = None) -> Summary:
    identifier = bill.get_absolute_url()
    statements = list(bill.get_debate_at_stage(reading).select_related('member', 'member__party'))
    if not statements:
        raise ValueError("No statements provided")
    
    major_speeches = get_major_speeches(statements)
    major_speeches_by_party = group_by_party(major_speeches)

    metadata = []
    summary_parts = []

    # Get overall summary from major_speeches
    prompt = bill_overview_prompt()
    transcript = get_transcript(major_speeches, para_urls=prompt.para_urls)
    resp, meta = call_llm(prompt, transcript)
    summary_parts.append(parse_bill_overview(resp, transcript))
    metadata.append(meta)

    # For each party, get individual summary bullets
    @retry(2, (LinkError, json.JSONDecodeError, KeyError, LLMProviderError))
    def _get_party_summary(party_name, party_speeches):
        prompt = bill_party_prompt()
        party_transcript = get_transcript(party_speeches, para_urls=prompt.para_urls)
        resp, meta = call_llm(prompt, party_transcript, model=llms.THINKING)
        party_summary = parse_bill_party(resp, party_transcript, party_name)

        summary_parts.append(party_summary)
        metadata.append(meta)

    # Start with the party of the bill's sponsor
    if bill.sponsor_member:
        sponsor_party = bill.sponsor_member.party.short_name
        if sponsor_party in major_speeches_by_party:
            _get_party_summary(sponsor_party, major_speeches_by_party[sponsor_party])
            del major_speeches_by_party[sponsor_party]

    for party_name, party_speeches in major_speeches_by_party.items():
        _get_party_summary(party_name, party_speeches)

    summary_text = "\n\n".join(summary_parts)
    summary = save_summary('stage_' + reading,
                            identifier, statements, metadata, summary_text=summary_text)
    return summary

def update_reading_summaries(session):
    debate_states = Statement.objects.filter(
        document__document_type='D', document__session=session, procedural=False,
        bill_debate_stage__in=('2', '3', 'report'))
    debates_avail = debate_states.values('bill_debated', 'bill_debate_stage').annotate(
        words=Sum("wordcount"), latest=Max("time"), count=Count("id"))
    
    tasks = []
    
    for row in debates_avail:
        if row['words'] < 2000:
            continue

        bill = Bill.objects.get(id=row['bill_debated'])
        try:
            summary = Summary.objects.get(
                summary_type='stage_' + row['bill_debate_stage'],
                identifier=bill.get_absolute_url())
            if row['count'] - summary.summarized_statement_count < 10:
                continue
        except Summary.DoesNotExist:
            pass

        tasks.append((bill, row['bill_debate_stage']))

    if tasks:
        print(f"{len(tasks)} summaries to generate")
        for bill, stage in tasks:
            summ = create_reading_summary(bill, stage)
            print(summ)