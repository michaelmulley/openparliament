"""Create an LLM summary of a Hansard."""

from itertools import groupby
import json
import logging

from parliament.hansards.models import Document
from parliament.hansards.utils import get_hansard_sections
from parliament.summaries.llm import LLMProviderError, llms
from parliament.summaries.models import Summary
from parliament.summaries.prompts import (section_prompt, parse_section, adjournment_prompt,
                                          parse_adjournment, qp_prompt, parse_qp,
                                          subheds_prompt, parse_subheds)
from .utils import LinkError, get_transcript, call_llm, retry, save_summary

logger = logging.getLogger(__name__)


def create_hansard_topics_summary(document) -> Summary | None:
    sections_obj = get_hansard_sections(document)
    if not sections_obj:
        return
    llm_metadata = []

    for section in sections_obj:
        meta = _summarize_hansard_section(section, document)
        if meta:
            if isinstance(meta, list):
                llm_metadata.extend(meta)
            else:
                llm_metadata.append(meta)

        if 'all_slugs' in section:
            del section['all_slugs']

    return save_summary('hansard_topics', document.get_absolute_url(), document.statement_set.all(),
                  llm_metadata, summary_json=sections_obj)

def section_task(section: dict) -> str | None:
    """Which kind of LLM summary (see prompts.TASKS) a section from get_hansard_sections gets.
    None means no summary."""
    heading = section['display_heading']
    if heading.lower() in ('petitions', 'statements by members'):
        return 'subheds'
    if heading == 'Question Period':
        return 'qp'
    if heading.lower() in ('adjournment proceedings', 'adjournment debates') and section['subheds']:
        return 'adjournment'
    if section['subheds']:
        return None
    return 'section'

@retry(2, (LinkError, json.JSONDecodeError, KeyError, LLMProviderError))
def _summarize_hansard_section(section, doc):
    statements = doc.statement_set.filter(slug__in=section['all_slugs'])

    task = section_task(section)
    if task == 'subheds':
        return _summarize_subheds(section, statements)
    elif task == 'qp':
        return _summarize_qp(section, statements)
    elif task == 'adjournment':
        return _summarize_adjournment(section, statements)
    elif task is None:
        return
    
    prompt = section_prompt(section['wordcount'], bool(section['bill_debated']))
    transcript = get_transcript(statements, para_urls=prompt.para_urls)
    resp, meta = call_llm(prompt, transcript)
    resp = parse_section(resp, transcript)
    section['summary_text'] = resp
    meta['tag'] = f"section - {section['display_heading']}"
    return meta

def _summarize_adjournment(section, statements):
    r = []
    metadata = []
    for h2, chunk_statements in groupby(statements, lambda s: s.h2_en):
        chunk_statements = list(chunk_statements)
        if sum(s.wordcount for s in chunk_statements if not s.procedural) < 300:
            continue

        prompt = adjournment_prompt()
        transcript = get_transcript(chunk_statements, para_urls=prompt.para_urls)
        resp, meta = call_llm(prompt, transcript)
        meta['tag'] = f"adjournment - {h2}"
        metadata.append(meta)
        json_resp = parse_adjournment(resp, transcript)
        json_resp['url'] = chunk_statements[0].urlcache
        r.append(json_resp)
    if r:
        if len(r) == 1:
            section['summary_text'] = r[0]['summary']
            section['display_heading'] = 'Adjournment Debate'
            if section.get('subheds'):
                section['display_heading'] += f" - {section['subheds'][0][0]}"
        else:
            section['summary_chunks'] = [f"[{c['topic']}]({c['url']}) {c['summary']}" for c in r]
        if 'subheds' in section:
            del section['subheds']
        return metadata

def _summarize_qp(section, statements):
    parties = dict()
    for s in statements:
        if s.member:
            parties.setdefault(s.member.party.short_name, []).append(s)

    summaries = []
    metadata = []
    for party_name, party_states in parties.items():
        if party_name == 'Independent':
            continue
        party_wordcount = sum(s.wordcount for s in party_states if not s.procedural)
        prompt = qp_prompt(party_wordcount, [s['summary'] for s in summaries])
        transcript = get_transcript(party_states, para_urls=prompt.para_urls)
        resp, meta = call_llm(prompt, transcript, model=llms.THINKING)
        summ = parse_qp(resp, transcript)
        summaries.append(dict(party_name=party_name, summary=summ))
        meta['tag'] = f"qp - {party_name}"
        metadata.append(meta)
    
    section['summary_chunks'] = [s['summary'] for s in summaries]
    if 'subheds' in section:
        del section['subheds'] 
    return metadata
    
def _summarize_subheds(section, statements):
    section_type = 'petition' if section['display_heading'].startswith('Petition') else 'statement'
    prompt = subheds_prompt(section_type)
    transcript = get_transcript(statements, para_urls=prompt.para_urls)
    resp, meta = call_llm(prompt, transcript)
    json_resp = parse_subheds(resp, transcript)
    for r in json_resp:
        r['slug'] = r['url'].rstrip('/').split('/')[-1]
    section['subheds'] = [(r['topic'], r['slug']) for r in json_resp]
    meta['tag'] = f"subheds - {section_type}"
    return meta

def update_hansard_summaries(n_most_recent=10, regenerate=False):
    docs = Document.debates.filter(public=True).order_by('-date')[:n_most_recent]
    for doc in docs:
        try:
            summary = Summary.objects.get(
                summary_type='hansard_topics',
                identifier=doc.get_absolute_url()
            )
            if (not regenerate) and abs(doc.statement_set.count() - summary.summarized_statement_count) < 10:
                    continue
        except Summary.DoesNotExist:
            pass

        try:
            print(doc)
            create_hansard_topics_summary(doc)
        except Exception as e:
            logger.exception(f"Error creating summary for {doc}: {e}")