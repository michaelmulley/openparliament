from collections.abc import Iterable
import json
import logging
import random
import re
import string
from time import sleep
from typing import Literal

from django.db.models import Sum, Max, Count

from parliament.hansards.models import Statement
from parliament.hansards.utils import get_major_speeches, group_by_party
from parliament.bills.models import Bill
from .llm import get_llm_response
from .models import Summary
from . import instructions

logger = logging.getLogger(__name__)

class LinkError(Exception):
    pass


def _statement_to_text(s: Statement) -> str:
    r = f"Name: {s.name_info['display_name']}\n"
    r += f"URL: {s.urlcache}\n"
    if s.member and not s.name_info.get('speaker'):
        r += f"Party: {s.member.party.short_name}\nRiding: {s.member.riding.name}\n"
    if s.name_info.get('post'):
        r += f"Title: {s.name_info['post']}\n"
    return r + "\n\n" + s.text_plain(include_paragraph_urls=True)

def get_transcript(statements: Iterable[Statement]) -> str:
    return "\n\n----\n\n".join(_statement_to_text(s) for s in statements)

def _load_json_response(llm_response: str) -> dict:
    if llm_response.startswith('```json'):
        llm_response = llm_response[7:-3].strip()
    try:
        return json.loads(llm_response)
    except json.JSONDecodeError as e:
        print("Error decoding JSON response")
        print(llm_response)
        raise

def retry(times: int, exceptions: tuple[Exception]):
    # https://stackoverflow.com/questions/50246304/using-python-decorators-to-retry-request
    def decorator(func):
        def newfn(*args, **kwargs):
            attempt = 0
            while attempt < times:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    print(
                        'Exception %r when attempting to run %s, attempt '
                        '%d of %d' % (e, func, attempt, times)
                    )
                    attempt += 1
            return func(*args, **kwargs)
        return newfn
    return decorator    

def check_markdown_links(summary_text: str, transcript: str) -> None:
    statement_links = set(re.findall(r'URL: (/[dc]\S+)\n', transcript))
    paragraph_links = set(re.findall(r'\n\[(/[dc]\S+#\S+)\] ', transcript))

    summary_links = set(re.findall(r'\]\(([^\)]+)\)', summary_text))

    transcript_links = statement_links | paragraph_links
    invalid_links = summary_links - transcript_links

    if invalid_links:
        raise LinkError(f"Invalid links in summary: {repr(invalid_links)}")

def _save_summary(summary_type: str, identifier: str,
                    statements: Iterable[Statement], 
                    summary_text: str,
                    metadata: list | dict) -> Summary:
    try:
        summary = Summary.objects.get(summary_type=summary_type, identifier=identifier)
    except Summary.DoesNotExist:
        summary = Summary(summary_type=summary_type, identifier=identifier)

    if not isinstance(statements, list):
        statements = list(statements)
    if isinstance(metadata, dict):
        metadata = [metadata]
    summary.summarized_statement_count = len(statements)
    summary.latest_statement_date = max(s.time for s in statements).date()
    transcript = get_transcript(statements)

    check_markdown_links(summary_text, transcript)
    summary.summary_text = summary_text
    summary.metadata = metadata
    summary.save()
    return summary

def _gen_string(length=6):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choices(characters, k=length))

def _call_llm_with_munged_urls(instructions: str, text: str, model: str | None = None,
                     chat_history = []) -> tuple[str, dict]:
    # In developing this, I often had problems where LLMs would hallucinate URLs when asked
    # to link back to specific paragraphs. But they weren't wholesale hallucinations, they were
    # little modifications to the actual URLs. I found this occurred much less often if the URLs
    # were opaque random strings instead of the actual long, meaningful URLs. So this 
    # function substitutes URLs with random strings, and then substitutes them back in the response.
    #
    # Same arguments and return values as get_llm_response.
    urls = {}
    urls_lookup = {}
    def replace_url(match):
        url = match.group(0)
        if url not in urls:
            new_url = None
            while new_url is None or new_url in urls_lookup:
                new_url = "/para/" + _gen_string()
            urls[url] = new_url
            urls_lookup[new_url] = url
        return urls[url]
    text2 = re.sub(r'/(?:debates|committees)/[^\s\]]+', replace_url, text)
    resp, meta = get_llm_response(instructions, text2, model=model, 
                                  chat_history=chat_history)
    def unreplace_url(match):
        try:
            return urls_lookup[match.group(0)]
        except KeyError:
            raise LinkError(f"Could not find URL {match.group(0)} in munged_urls lookup")
    resp2 = re.sub(r'/para/[^\s\]\)"]+', unreplace_url, resp)
    return (resp2, meta)


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
    resp, meta = get_llm_response(instructions.BILL_SUMMARY_FROM_SPEECHES, get_transcript(major_speeches))
    summary_parts.append(resp)
    metadata.append(meta)

    # For each party, get individual summary bullets
    @retry(1, (LinkError, json.JSONDecodeError, KeyError))
    def _get_party_summary(party_name, party_speeches):
        party_transcript = get_transcript(party_speeches)
        resp, meta = _call_llm_with_munged_urls(instructions.BILL_READING_INSTRUCTIONS_PARTY, party_transcript)
        json_resp = _load_json_response(resp)
        party_summary = f"**{party_name}**\n\n"
        for bullet in json_resp:
            party_summary += f"- [{bullet['headline']}]({bullet['source_paragraph_url']}): {bullet['summary']}\n"
        check_markdown_links(party_summary, party_transcript)

        summary_parts.append(party_summary)
        metadata.append(meta)

    # Start with the party of the bill's sponsor
    if bill.sponsor_member:
        sponsor_party = bill.sponsor_member.party.short_name
        _get_party_summary(sponsor_party, major_speeches_by_party[sponsor_party])
        del major_speeches_by_party[sponsor_party]

    for party_name, party_speeches in major_speeches_by_party.items():
        _get_party_summary(party_name, party_speeches)

    summary_text = "\n\n".join(summary_parts)
    summary = _save_summary('stage_' + reading,
                            identifier, statements, summary_text, metadata)
    return summary

def update_reading_summaries(session):
    debate_states = Statement.objects.filter(
        document__document_type='D', document__session=session, procedural=False,
        bill_debate_stage__in=('2', '3', 'report'))
    debates_avail = debate_states.values('bill_debated', 'bill_debate_stage').annotate(
        words=Sum("wordcount"), latest=Max("time"), count=Count("id"))
    
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

        summ = create_reading_summary(bill, row['bill_debate_stage'])
        print(summ)
        sleep(21)
