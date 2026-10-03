"""Validation of LLM summary responses.

No Django imports here: this module is shared by the app and by the promptfoo
evals in parliament/summaries/eval/.
"""
import json
import random
import re
import string


class LinkError(Exception):
    pass


# Transcripts give each statement a "URL: /..." header line, and (optionally) start
# each paragraph with "[/url#fragment] ". URLs may be real (/debates/..., /committees/...)
# or munged (/st/xxxxxx); see munge_urls.
def transcript_statement_urls(transcript: str) -> set[str]:
    return set(re.findall(r'URL: (/\S+)\n', transcript))

def transcript_paragraph_urls(transcript: str) -> set[str]:
    return set(re.findall(r'\n\[(/\S+)\] ', transcript))

def markdown_links(text: str) -> list[tuple[str, str]]:
    """Returns (link_text, url) pairs for Markdown links in the text."""
    return re.findall(r'\[([^\]]+)\]\(([^\)]+)\)', text)

def check_markdown_links(summary_text: str, transcript: str) -> None:
    summary_links = set(url for _, url in markdown_links(summary_text))
    transcript_links = transcript_statement_urls(transcript) | transcript_paragraph_urls(transcript)
    invalid_links = summary_links - transcript_links

    if invalid_links:
        raise LinkError(f"Invalid links in summary: {repr(invalid_links)}")

def strip_markdown_links(s: str) -> str:
    """Remove markdown links from a string."""
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1', s)

def check_length(text: str, length: int) -> None:
    text = strip_markdown_links(text)
    if len(text) > length:
        raise ValueError(f"Text exceeds {length} characters: {len(text)} {text}")

def load_json_response(llm_response: str) -> dict | list:
    llm_response = llm_response.strip()
    if llm_response.startswith('```json'):
        llm_response = llm_response[7:-3].strip()
    return json.loads(llm_response)

def gen_string(length=6, rng: random.Random | None = None) -> str:
    """Make a random string."""
    characters = string.ascii_letters + string.digits
    return ''.join((rng or random).choices(characters, k=length))

def munge_urls(text: str, rng: random.Random | None = None) -> tuple[str, dict[str, str]]:
    """Replaces transcript URLs with short opaque ones (/st/xxxxxx).

    Returns the new text and a lookup dict of {munged_url: original_url}.
    """
    # In developing this, I often had problems where LLMs would hallucinate URLs when asked
    # to link back to specific paragraphs. But they weren't wholesale hallucinations, they were
    # little modifications to the actual URLs. I found this occurred much less often if the URLs
    # were opaque random strings instead of the actual long, meaningful URLs.
    urls = {}
    urls_lookup = {}
    def replace_url(match):
        url = match.group(0)
        if url not in urls:
            new_url = None
            while new_url is None or new_url in urls_lookup:
                new_url = "/st/" + gen_string(rng=rng)
            urls[url] = new_url
            urls_lookup[new_url] = url
        return urls[url]
    return re.sub(r'/(?:debates|committees)/[^\s\]]+', replace_url, text), urls_lookup

def unmunge_urls(text: str, urls_lookup: dict[str, str]) -> str:
    def unreplace_url(match):
        try:
            return urls_lookup[match.group(0)]
        except KeyError:
            raise LinkError(f"Could not find URL {match.group(0)} in munged_urls lookup")
    return re.sub(r'/st/[^\s\]\)"]+', unreplace_url, text)
