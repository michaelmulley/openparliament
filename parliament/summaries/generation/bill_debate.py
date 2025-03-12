import json
import logging
from typing import Literal

from django.db.models import Sum, Max, Count

from parliament.hansards.models import Statement
from parliament.hansards.utils import get_major_speeches, group_by_party
from parliament.bills.models import Bill
from parliament.summaries.llm import get_llm_response, LLMProviderError, llms
from parliament.summaries.models import Summary

from .utils import (LinkError, get_transcript, call_llm_with_munged_urls,
                    load_json_response, check_markdown_links, retry, save_summary,
                    check_length)

logger = logging.getLogger(__name__)

BILL_SUMMARY_FROM_SPEECHES = """You will be provided with a transcript of the speeches at the reading of a bill in the Canadian House of Commons. Based on the speeches, please write a summary of the bill in 15 to 45 words.

The people speaking are members of different parties and have different points of view. You should summarize the bill in a neutral way, without adopting any party's point of view.

Respond with only the summary, no extra headings or comments.
"""

BILL_READING_INSTRUCTIONS_PARTY = """You will be provided with a transcript of the speeches by members of one political party at the reading of a bill in the Canadian House of Commons. Please summarize the party's position on the bill. 

Before each speech, the name of the member speaking is provided. Most paragraphs begin with a URL for that paragraph in [square brackets]. (URLs are relative, that's fine, use them as-is.) Speeches are separated with "----".

Provide 1-4 bullet points summarizing the party's position on the bill. Return your summary in JSON. (Include only the JSON object for the summary in your response.)

Be direct and succinct. In general, use the present tense. Your summary will have the party name as a heading, so you don't need to repeat it in every bullet.

Use the following structure:
[
    {
        "headline": "2-6 word phrase establishing the topic of this point. Use sentence case, not Title Case.",
        "source_paragraph_url": "Relative URL, copied exactly from the transcript provided, to the paragraph where the discussion that best supports this point begins.",
        "summary": "8 to 40 words on this summary point"
    }
]

Here's an example (for a different bill):
[
    {
        "headline": "Supports bill C-95",
        "source_paragraph_url": "/st/h38f",
        "summary": "The Bloc supports the bill, emphasizing the need to enhance transparency and build trust between victims and the justice system."
    },
    {
        "headline": "Quebec's leadership",
        "source_paragraph_url": "/st/72HHd",
        "summary": "Members note Quebec's initiatives, such as specialized courts and electronic monitoring, as models in improving victim protection and restoring trust in the justice system."
    },
    {
        "headline": "Focus on violence against women",
        "source_paragraph_url": "/st/9KKp4d",
        "summary": "Christine Guy-Marcil highlights an increase in femicide and domestic violence. She argues that Parliament has a responsibility to try and reverse the trend, that concrete action is slow in coming, but that this bill is a step to improve victims' experience with the justice system and start rebuilding trust."
    }
]

"""

BILL_READING_INSTRUCTIONS_PARTY_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "headline": {"type":"STRING"},
            "source_paragraph_url": {"type":"STRING"},
            "summary": {"type":"STRING"}
        }
    }
}

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
    resp, meta = get_llm_response(BILL_SUMMARY_FROM_SPEECHES, get_transcript(major_speeches, para_urls=True), temperature=0.7)
    check_length(resp, 420)
    summary_parts.append(resp)
    metadata.append(meta)

    # For each party, get individual summary bullets
    @retry(2, (LinkError, json.JSONDecodeError, KeyError, LLMProviderError))
    def _get_party_summary(party_name, party_speeches):
        party_transcript = get_transcript(party_speeches, para_urls=True)
        resp, meta = call_llm_with_munged_urls(BILL_READING_INSTRUCTIONS_PARTY, party_transcript,
                                                json=BILL_READING_INSTRUCTIONS_PARTY_SCHEMA,
                                                model=llms.THINKING, temperature=0.7)
        json_resp = load_json_response(resp)
        party_summary = f"**{party_name}**\n\n"
        for bullet in json_resp:
            party_summary += f"- [{bullet['headline']}]({bullet['source_paragraph_url']}): {bullet['summary']}\n"
        check_markdown_links(party_summary, party_transcript)
        check_length(party_summary, 1600)

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