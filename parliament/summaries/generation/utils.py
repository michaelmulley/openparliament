from collections.abc import Iterable
import json
import logging
import random
import re
import string
from time import sleep

from parliament.hansards.models import Statement
from parliament.summaries.llm import get_llm_response, LLMProviderError
from parliament.summaries.models import Summary

logger = logging.getLogger(__name__)

class LinkError(Exception):
    pass


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

def load_json_response(llm_response: str) -> dict:
    if llm_response.startswith('```json'):
        llm_response = llm_response[7:-3].strip()
    try:
        return json.loads(llm_response)
    except json.JSONDecodeError as e:
        print("Error decoding JSON response")
        print(llm_response)
        raise

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

def check_markdown_links(summary_text: str, transcript: str) -> None:
    statement_links = set(re.findall(r'URL: (/[dc]\S+)\n', transcript))
    paragraph_links = set(re.findall(r'\n\[(/[dc]\S+#\S+)\] ', transcript))

    summary_links = set(re.findall(r'\]\(([^\)]+)\)', summary_text))

    transcript_links = statement_links | paragraph_links
    invalid_links = summary_links - transcript_links

    if invalid_links:
        raise LinkError(f"Invalid links in summary: {repr(invalid_links)}")

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
        existing_summary.update(summary_type=summary_type + '_archived_' + _gen_string(5))
    
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

def _gen_string(length=6):
    """Make a random string."""
    characters = string.ascii_letters + string.digits
    return ''.join(random.choices(characters, k=length))

def strip_markdown_links(s: str) -> str:
    """Remove markdown links from a string."""
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1', s)

def check_length(text: str, length: int) -> None:
    text = strip_markdown_links(text)
    if len(text) > length:
        raise ValueError(f"Text exceeds {length} characters: {len(text)} {text}")

def call_llm_with_munged_urls(instructions: str, text: str, model: str | None = None,
                     **kwargs) -> tuple[str, dict]:
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
                new_url = "/st/" + _gen_string()
            urls[url] = new_url
            urls_lookup[new_url] = url
        return urls[url]
    text2 = re.sub(r'/(?:debates|committees)/[^\s\]]+', replace_url, text)
    resp, meta = get_llm_response(instructions, text2, model=model, **kwargs)
    def unreplace_url(match):
        try:
            return urls_lookup[match.group(0)]
        except KeyError:
            raise LinkError(f"Could not find URL {match.group(0)} in munged_urls lookup")
    resp2 = re.sub(r'/st/[^\s\]\)"]+', unreplace_url, resp)
    return (resp2, meta)