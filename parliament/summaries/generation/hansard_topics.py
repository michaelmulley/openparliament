"""Create an LLM summary of a Hansard."""

from itertools import groupby
import json
import logging

from parliament.hansards.models import Document
from parliament.hansards.utils import get_hansard_sections
from parliament.summaries.llm import get_llm_response, LLMProviderError, llms
from parliament.summaries.models import Summary
from .utils import (LinkError, get_transcript, call_llm_with_munged_urls,
                    load_json_response, check_markdown_links, retry, save_summary,
                    check_length, strip_markdown_links)

logger = logging.getLogger(__name__)


HANSARD_TOPIC_INSTRUCTIONS_INTRO = """You will be provided with a transcript of a debate in the Canadian House of Commons. These typically include multiple Members of Parliament speaking, from different political parties and with different points of view.
"""

HANSARD_TOPIC_SUBHED_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "url": {"type":"STRING"},
            "topic": {"type":"STRING"}
        }
    }
}

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

@retry(2, (LinkError, json.JSONDecodeError, KeyError, LLMProviderError))
def _summarize_hansard_section(section, doc):
    statements = doc.statement_set.filter(slug__in=section['all_slugs'])

    if section['display_heading'].lower() in ('petitions', 'statements by members'):
        return _summarize_subheds(section, statements)
    
    if section['display_heading'] == 'Question Period':
        return _summarize_qp(section, statements)
    
    if section['display_heading'].lower() in ('adjournment proceedings', 'adjournment debates') and section['subheds']:
        return _summarize_adjournment(section, statements)
    
    if section['subheds']:
        return
    
    if section['wordcount'] < 1500:
        num_words = "35 words or less"
    elif section['wordcount'] > 15000:
        num_words = "no more than 80 words"
    else:
        num_words = "65 words or less"

    instructions = HANSARD_TOPIC_INSTRUCTIONS_INTRO
    
    instructions += """Please summarize the topic of the transcript in {num_words}. Respond with only the summary, no extra text. Be direct and succinct. In general, use the present tense. The summary should be politically neutral, so if you use any charged or partisan language, ensure that it's clear which party or person it comes from.""".format(num_words=num_words)

    request_internal_links = section['wordcount'] > 2000
    if request_internal_links:
        instructions += """\nIf relevant, you can link words or phrases (no longer than 4 words) within your summary to the speech that phrase refers to. Use Markdown syntax for links. URLs are provided for each speech in the transcript; it's a relative URL, use it as-is (remember it begins with a / slash). Make sure the linked speech is fully consistent with the link text and context: double-check that the linked speech matches the topic of the link text, that the party of the person speaking is consistent with what the summary sentence implies, etc. If you're not sure whether the link is consistent and accurate, leave it out. Try not to link to the same speech more than once.\n\n"""    
    
    if section['bill_debated']:
        instructions += """\nThis transcript appears to be about a bill. Your summary should begin with "The bill". (You don't need to include the bill number, it will be displayed beside your summary.)"""
    else:
        instructions += """\nYour summary should begin with either "Members" or the name of a specific MP or party.

        An example: "Members debate a report from the Committee on Veterans Affairs regarding survivor pension benefits for spouses who married veterans after the age of 60, focusing on the discriminatory "gold digger clause" and the need for immediate action to eliminate this inequity. They also discuss broader issues facing veterans, including [cost of living](/st/J387Hd), [access to services](/st/9087Jf), and [historical treatment](/st/987Hss) by previous governments."

        """
    if not request_internal_links:
        instructions = strip_markdown_links(instructions)    
        
    transcript = get_transcript(statements, para_urls=False)
    resp, meta = call_llm_with_munged_urls(instructions, transcript, model=llms.THINKING, temperature=0.7)
    check_markdown_links(resp, transcript)
    check_length(resp, 850)
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

        instructions = HANSARD_TOPIC_INSTRUCTIONS_INTRO
        instructions += """This transcript should be a short debate (an "adjournment debate") on a specific topic. Summarize the debate in 50 words or less. These debates typically involve only two people; if that's the case, you should mention them by name. Be direct and succinct. In general, use the present tense.
        
        Additionally, provide a topic heading of 2 to 6 words for the debate (e.g. "Cost of living for families"). Use sentence case for the topic heading, capitalizing the first letter but otherwise not capitalizing common nouns. Respond with a JSON object containing "topic" and "summary" keys. Here's an example:

        {
            "topic": "Indigenous procurement",
            "summary": "Garnett Genuis accuses the government of turning a blind eye to systemic fraud within the Indigenous procurement program, where non-Indigenous companies lie to obtain contracts intended for Indigenous businesses. Jenica Atwin defends the program as vital for economic reconciliation, highlighting its support from Indigenous leaders."
        }

        And another example:

        {
            "topic": "Cost of living for families",
            "summary": "Callie Blitzen describes how families are struggling with inflation, and asks what the government is doing. Jeff Dung cites the subsidized child care program and child benefit. Blitzen also criticizes the government's \\\"radical eco agenda\\\", and Dung argues that we need to fight climate change to give kids a good future."
        }
        """

        SCHEMA = {
            "type": "OBJECT",
            "properties": {
                "topic": {"type":"STRING"},
                "summary": {"type":"STRING"}
            }
        } # Gemini really does not like this schema for some reason?

        transcript = get_transcript(chunk_statements, para_urls=False)
        resp, meta = get_llm_response(instructions, transcript, json=True)
        meta['tag'] = f"adjournment - {h2}"
        metadata.append(meta)
        json_resp = load_json_response(resp)
        json_resp['url'] = chunk_statements[0].urlcache
        check_length(json_resp['topic'], 75)
        check_length(json_resp['summary'], 600)
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

QP_INSTRUCTIONS = """Question Period in the Canadian House of Commons consists of short spoken questions and answers from different Members of Parliament, belonging to different political parties. You will be provided with a transcript of what the members of one party said during a specific Question Period.

For each speech segment, a URL is provided. It's a relative URL -- that's fine, use it as-is. Remember, it begins with a / slash.

Your task is to provide a brief summary of the main subjects this party focuses on during this Question Period. The summary should be less than {wordcount} words, in a single, short paragraph.

Inside the summary text, wherever reasonable, link words or phrases (no longer than 4 words) to the relevant speech segment where someone from the party discusses that topic. Use Markdown syntax for the links. Don't add any extra text to accommodate links -- for example, don't add footnote-style links like (1). Make sure the linked speech is fully consistent with the link text and context: double-check that the linked speech matches the topic of the link text, that the party of the person speaking is consistent with what the summary sentence implies, etc. Don't link to the same URL more than once.

Your summaries should begin with e.g. "The **Liberals**", with the party name in bold. To keep things brief, you usually shouldn't mention the names of the members speaking.

Respond with only the summary text, no headings, introductions, or anything else extraneous.

Here are two examples:

The **Conservatives** criticize the Liberal government's [economic management](/st/8HHj3). They point to the [$62-billion deficit](/st/p9S2Kx), higher than the previous $40-billion "guardrail." They [call for an election](/st/fj3PPx) (framing it as a "carbon tax election") and accuse the Prime Minister of [losing the confidence](/st/j38FF) of his cabinet, caucus, and Canadians.

The **Liberals** defend their [fiscal record](/st/HjF9I), emphasizing Canada's debt-to-GDP ratio as the [best in the G7](/st/2482K) and celebrating their investments in programs like [$10-a-day childcare](/st/1PPwJJ) and dental care. They focus on their preparations for [working with the incoming Trump administration](/st/0KK2dy), [border security measures](/st/llskPD), and their investments in [clean electricity](/st/HPLKw3).

"""

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
        if party_wordcount > 1500:
            summary_wordcount = 60
        elif party_wordcount > 200:
            summary_wordcount = 40
        else:
            summary_wordcount = 20

        prompt = QP_INSTRUCTIONS.format(wordcount=summary_wordcount)
        if summaries:
            prompt += "For context, here are summaries you've already written for other parties during this Question Period, which will be shown to readers alongside the one you're writing now:\n\n"
            prompt += "\n\n".join(s['summary'] for s in summaries)

        transcript = get_transcript(party_states, para_urls=False)
        resp, meta = call_llm_with_munged_urls(prompt, transcript,
                                               model=llms.THINKING)
        check_markdown_links(resp, transcript)
        summ = resp.strip().replace("\n", " ").replace('**Bloc Québécois**', '**Bloc**')
        check_length(summ, 750)
        summaries.append(dict(party_name=party_name, summary=summ))
        meta['tag'] = f"qp - {party_name}"
        metadata.append(meta)
    
    section['summary_chunks'] = [s['summary'] for s in summaries]
    if 'subheds' in section:
        del section['subheds'] 
    return metadata
    
def _summarize_subheds(section, statements):
    instructions = HANSARD_TOPIC_INSTRUCTIONS_INTRO
    instructions += "For each statement, a URL is provided. It's a relative URL -- that's fine, use it as-is.\n\n"

    section_type = 'petition' if section['display_heading'].startswith('Petition') else 'statement'
    if section_type == 'petition':
        instructions += "This transcript should consist largely of members introducing petitions.\n\n"
    else:
        instructions += "This transcript should consist largely of members making brief statements on topics of their choosing.\n\n"

    instructions += f"For each {section_type}, provide the URL and a 1 to 6 word topic heading for the {section_type}.\n\n"

    instructions += """Respond in JSON, providing a "url" and "topic" for each relevant item. Include only the JSON object in your response. Here's an example:
    [ {"url": "/st/h987f", "topic": "Foreign interference in elections"},
        {"url": "/st/88JJF", "topic": "A regional aquatic centre"},
        {"url": "/st/825cF", "topic": "Funding for women's shelters"},
        {"url": "/st/V4h82f", "topic": "Theatre company head Amélie Duceppe"} ]
    """
    transcript = get_transcript(statements, para_urls=False)
    resp, meta = call_llm_with_munged_urls(instructions, transcript, json=True)
                                            # json_schema=HANSARD_TOPIC_SUBHED_SCHEMA)
    json_resp = load_json_response(resp)
    for r in json_resp:
        r['slug'] = r['url'].rstrip('/').split('/')[-1]
        if r['slug'] not in section['all_slugs']:
            raise LinkError(f"Invalid URL {r['url']} in subhed response")
        check_length(r['topic'], 75)
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