from collections.abc import Iterable
import logging
from time import sleep

from parliament.hansards.models import Statement
from parliament.summaries.checks import (LinkError, check_markdown_links,
                                         munge_urls, unmunge_urls, gen_string)
from parliament.summaries.llm import get_llm_response, LLMProviderError
from parliament.summaries.models import Summary
from parliament.summaries.prompts import Prompt

logger = logging.getLogger(__name__)


def _statement_to_text(s: Statement, para_urls=True) -> str:
    r = f"Name: {s.name_info['display_name']}\n"
    r += f"URL: {s.urlcache}\n"
    if s.member and not s.name_info.get('speaker'):
        r += f"Party: {s.member.party.short_name}\nRiding: {s.member.riding.name}\n"
    if s.name_info.get('post'):
        r += f"Title: {s.name_info['post']}\n"
    return r + "\n\n" + s.text_plain(include_paragraph_urls=para_urls)

def get_transcript(statements: Iterable[Statement], para_urls: bool) -> str:
    return "\n\n----\n\n".join(_statement_to_text(s, para_urls=para_urls) for s in statements)

def retry(times: int, exceptions: tuple[type[Exception], ...]):
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
                    if isinstance(e, LLMProviderError):
                        sleep(45)
            return func(*args, **kwargs)
        return newfn
    return decorator    

def save_summary(summary_type: str, identifier: str,
                    statements: Iterable[Statement], 
                    metadata: list | dict,
                    *, summary_text: str = '',
                    summary_json: list | dict | None = None) -> Summary:
    
    if not isinstance(statements, list):
        statements = list(statements)
    if isinstance(metadata, dict):
        metadata = [metadata]
    
    if summary_text:
        transcript = get_transcript(statements, para_urls=True)
        check_markdown_links(summary_text, transcript)

    existing_summary = Summary.objects.filter(summary_type=summary_type, identifier=identifier)
    if existing_summary.exists():
        existing_summary.update(summary_type=summary_type + '_archived_' + gen_string(5))
    
    summary = Summary(summary_type=summary_type, identifier=identifier)

    if summary_text:
        summary.summary_text = summary_text
    elif summary_json:
        summary.summary_json = summary_json
    else:
        raise ValueError("No summary text or JSON provided")
    
    summary.summarized_statement_count = len(statements)
    summary.latest_statement_date = max(s.time for s in statements).date()
    summary.metadata = metadata
    summary.save()
    return summary

def call_llm(prompt: Prompt, transcript: str, model: str | None = None) -> tuple[str, dict]:
    """Sends the prompt and transcript to the LLM, munging URLs if the prompt calls for it.

    Same return values as get_llm_response."""
    if not prompt.munge_urls:
        return get_llm_response(prompt.instructions, transcript, model=model, json=prompt.json)
    munged, urls_lookup = munge_urls(transcript)
    resp, meta = get_llm_response(prompt.instructions, munged, model=model, json=prompt.json)
    return unmunge_urls(resp, urls_lookup), meta
