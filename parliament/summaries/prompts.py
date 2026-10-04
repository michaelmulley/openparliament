"""Prompts for LLM summaries, and parsers/validators for their responses.

Each kind of LLM call has a builder that returns a Prompt, and a parse_ function that
validates the response (raising an exception if it's unacceptable) and returns it in
the form the app stores. The prompt text is in Jinja templates in prompt_templates/.

No Django imports here: this module is shared by the app (summaries/generation/) and by
the promptfoo evals in parliament/summaries/eval/, so the evals run the real prompts
and the real validation.
"""
from dataclasses import dataclass
from pathlib import Path

import jinja2

from .checks import (LinkError, check_length, check_markdown_links, load_json_response,
                     transcript_statement_urls)


@dataclass
class Prompt:
    instructions: str
    # True to request a JSON object; a dict to require a JSON schema
    json: bool | dict = False
    # Should the transcript begin each paragraph with its URL?
    para_urls: bool = False
    # Should URLs in the transcript be replaced with short opaque ones? See checks.munge_urls
    munge_urls: bool = True


_templates = jinja2.Environment(
    loader=jinja2.FileSystemLoader(Path(__file__).parent / 'prompt_templates'),
    undefined=jinja2.StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
)

def render(template_name: str, **context) -> str:
    return _templates.get_template(template_name).render(**context).strip()


##########################
# Bill debates
##########################

def bill_overview_prompt() -> Prompt:
    return Prompt(render('bill_overview.j2'), para_urls=True, munge_urls=False)

def parse_bill_overview(resp: str, transcript: str) -> str:
    check_length(resp, 420)
    return resp


BILL_PARTY_SCHEMA = {
    "type": "object",
    "properties": {
        "bullet_points": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "headline": {"type": "string"},
                    "source_paragraph_url": {"type": "string"},
                    "summary": {"type": "string"}
                },
                "required": ["headline", "source_paragraph_url", "summary"],
                "additionalProperties": False
            }
        }
    },
    "required": ["bullet_points"],
    "additionalProperties": False
}

def bill_party_prompt() -> Prompt:
    """One party's speeches at a reading of a bill."""
    return Prompt(render('bill_party.j2'), json=BILL_PARTY_SCHEMA, para_urls=True)

def parse_bill_party(resp: str, transcript: str, party_name: str) -> str:
    """Returns the party's section of the summary, as Markdown."""
    bullets = load_json_response(resp)["bullet_points"]
    party_summary = f"**{party_name}**\n\n"
    for bullet in bullets:
        party_summary += f"- [{bullet['headline']}]({bullet['source_paragraph_url']}): {bullet['summary']}\n"
    check_markdown_links(party_summary, transcript)
    check_length(party_summary, 1600)
    return party_summary


##########################
# Hansard topics
##########################

def section_word_limit(wordcount: int) -> int:
    if wordcount < 1500:
        return 35
    elif wordcount > 15000:
        return 80
    return 65

def section_links_requested(wordcount: int) -> bool:
    return wordcount > 2000

def section_prompt(wordcount: int, bill_debated: bool) -> Prompt:
    """A general section of a Hansard (one that isn't one of the specific types below)."""
    return Prompt(render('section.j2',
                         max_words=section_word_limit(wordcount),
                         links=section_links_requested(wordcount),
                         bill_debated=bill_debated))

def parse_section(resp: str, transcript: str) -> str:
    check_markdown_links(resp, transcript)
    check_length(resp, 850)
    return resp


ADJOURNMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "topic": {"type": "string"},
        "summary": {"type": "string"}
    },
    "required": ["topic", "summary"],
    "additionalProperties": False
}

def adjournment_prompt() -> Prompt:
    """A single adjournment debate (there are usually several in the Adjournment Proceedings section)."""
    return Prompt(render('adjournment.j2'), json=ADJOURNMENT_SCHEMA, munge_urls=False)

def parse_adjournment(resp: str, transcript: str) -> dict:
    """Returns a dict with "topic" and "summary" keys."""
    r = load_json_response(resp)
    check_length(r['topic'], 75)
    check_length(r['summary'], 600)
    return r


def qp_word_limit(party_wordcount: int) -> int:
    if party_wordcount > 1500:
        return 60
    elif party_wordcount > 200:
        return 40
    return 20

def qp_prompt(party_wordcount: int, prior_summaries: list[str]) -> Prompt:
    """One party's contributions to a Question Period.

    prior_summaries are the summaries already written for other parties in the same QP."""
    return Prompt(render('qp.j2', max_words=qp_word_limit(party_wordcount),
                         prior_summaries=prior_summaries))

def parse_qp(resp: str, transcript: str) -> str:
    check_markdown_links(resp, transcript)
    summ = resp.strip().replace("\n", " ").replace('**Bloc Québécois**', '**Bloc**')
    check_length(summ, 750)
    return summ


SUBHEDS_SCHEMA = {
    "type": "object",
    "properties": {
        "headings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "topic": {"type": "string"}
                },
                "required": ["url", "topic"],
                "additionalProperties": False
            }
        }
    },
    "required": ["headings"],
    "additionalProperties": False
}

def subheds_prompt(section_type: str) -> Prompt:
    """Topic headings for each item in Petitions or Statements by Members.

    section_type is 'petition' or 'statement'."""
    return Prompt(render('subheds.j2', section_type=section_type), json=SUBHEDS_SCHEMA)

def parse_subheds(resp: str, transcript: str) -> list[dict]:
    """Returns a list of {"url": ..., "topic": ...} dicts."""
    items = load_json_response(resp)["headings"]
    statement_urls = transcript_statement_urls(transcript)
    for r in items:
        if r['url'] not in statement_urls:
            raise LinkError(f"Invalid URL {r['url']} in subhed response")
        check_length(r['topic'], 75)
    return items


# The kinds of LLM call, for the evals: task name -> (prompt builder, response parser)
TASKS = {
    'bill_overview': (bill_overview_prompt, parse_bill_overview),
    'bill_party': (bill_party_prompt, parse_bill_party),
    'section': (section_prompt, parse_section),
    'adjournment': (adjournment_prompt, parse_adjournment),
    'qp': (qp_prompt, parse_qp),
    'subheds': (subheds_prompt, parse_subheds),
}
