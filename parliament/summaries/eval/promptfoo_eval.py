"""promptfoo hooks for evaluating the summary prompts. See README.md.

promptfoo calls these functions (they're referenced from promptfooconfig.yaml):
- load_tests: builds test cases from evalset.json (made by `manage.py export_summary_evalset`)
- summary_prompt: builds the prompt for a test case, using the app's own prompt builders
- check_valid: does the response pass the app's own validation? (as in production)
- check_instructions: does it follow the prompt's stated constraints (word limits etc.)?
- readable_output / link_report: transform responses into what the LLM judges grade

This runs outside Django, so it only imports the Django-free summaries.prompts and
summaries.checks modules.
"""
import json
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from parliament.summaries.checks import load_json_response, markdown_links, strip_markdown_links
from parliament.summaries.prompts import TASKS, qp_word_limit, section_links_requested, section_word_limit

EVAL_DIR = Path(__file__).resolve().parent

##########################
# Prompts
##########################

def summary_prompt(context: dict) -> dict:
    v = context['vars']
    build, _ = TASKS[v['task']]
    prompt = build(**v['prompt_args'])
    messages = [
        {'role': 'system', 'content': prompt.instructions},
        {'role': 'user', 'content': v['transcript']},
    ]
    config = {}
    # Mirrors llm._get_llm_response_openrouter
    if isinstance(prompt.json, dict):
        config['response_format'] = {
            'type': 'json_schema',
            'json_schema': {'name': 'op-json', 'strict': True, 'schema': prompt.json},
        }
    elif prompt.json:
        config['response_format'] = {'type': 'json_object'}
    return {'prompt': json.dumps(messages), 'config': config}


##########################
# Test cases
##########################

JUDGE_NOTES = {
    'bill_overview': "The summary describes the bill being debated.",
    'bill_party': "The transcript contains only speeches by members of one party; the summary describes that party's position on the bill. It's displayed under the party's name as a heading, so readers understand each bullet point as that party's position.",
    'section': "",
    'adjournment': "",
    'qp': "The transcript contains only what members of one party said during Question Period; the summary describes the subjects that party focused on.",
    'subheds': "The output is a list of topic headings, one per statement or petition.",
}

ACCURACY_RUBRIC = """You are checking an automatically generated summary of a transcript from the Canadian House of Commons for factual accuracy. {note}

The summary passes only if every claim in it is supported by the transcript: no invented facts, figures, events or positions; positions and statements attributed to the correct party or person; nothing misrepresented or distorted. Omissions are fine: it's a brief summary. Ignore formatting and URLs.

Give a score from 0 to 1, where 1 is fully accurate. In your reason, quote each inaccurate or unsupported claim and explain briefly.

<transcript>
{{{{transcript}}}}
</transcript>"""

NEUTRALITY_RUBRIC = """The output is an automatically generated summary of debate in the Canadian House of Commons, for a non-partisan website. {note}

It must be politically neutral. It may report partisan claims and charged language, but it must be clear which party or person they come from; the summary itself must not adopt any party's framing, take sides, or editorialize.

Give a score from 0 to 1, where 1 is fully neutral. In your reason, quote any problematic phrase."""

LINK_RUBRIC = """The output below is an automatically generated summary of debate in the Canadian House of Commons, followed by a list of its links. For each link you're shown the link text, the sentence or bullet point it appears in, and the speech or paragraph it links to (with the speaker's name and party).

A link is acceptable if the linked speech or paragraph supports the link text in the context where it appears: the subject matches, and the speaker is consistent with what the surrounding text implies (e.g. a sentence about what the Conservatives argue should not link to a Liberal's speech). For topic headings, the heading must accurately describe the linked statement. A link whose target wasn't found is unacceptable.

Score is the fraction of links that are acceptable. Pass only if every link is acceptable. In your reason, list the unacceptable links by number, with a brief explanation. If there are no links, pass with a score of 1."""

# Which tasks produce links to the transcript
LINK_TASKS = {'bill_party', 'section', 'qp', 'subheds'}


def load_tests(config: dict | None = None) -> list[dict]:
    config = config or {}
    evalset = EVAL_DIR / config.get('evalset', 'evalset.json')
    if not evalset.exists():
        raise FileNotFoundError(f"{evalset} not found: run `manage.py export_summary_evalset` first")
    cases = json.loads(evalset.read_text())
    judges = os.environ.get('SUMMARY_EVAL_JUDGES', '1') != '0'

    tests = []
    for case in cases:
        task = case['task']
        asserts = [
            {'type': 'python', 'value': 'file://promptfoo_eval.py:check_valid', 'metric': 'valid'},
            {'type': 'python', 'value': 'file://promptfoo_eval.py:check_instructions', 'metric': 'instructions'},
        ]
        if judges:
            note = JUDGE_NOTES[task]
            if task != 'subheds':  # for subheds, accuracy is what the link judge checks
                asserts.append({'type': 'llm-rubric', 'metric': 'accuracy',
                                'value': ACCURACY_RUBRIC.format(note=note),
                                'transform': 'file://promptfoo_eval.py:readable_output'})
            asserts.append({'type': 'llm-rubric', 'metric': 'neutrality',
                            'value': NEUTRALITY_RUBRIC.format(note=note),
                            'transform': 'file://promptfoo_eval.py:readable_output'})
            if task in LINK_TASKS and _links_requested(case):
                asserts.append({'type': 'llm-rubric', 'metric': 'link_accuracy',
                                'value': LINK_RUBRIC,
                                'transform': 'file://promptfoo_eval.py:link_report'})

        current = case['current_output']
        if isinstance(current, list):  # subheds
            current = "\n".join(f"- {topic}" for topic, _ in current)
        tests.append({
            'description': f"{task}: {case['label']}",
            'vars': {
                'task': task,
                'source': 'https://openparliament.ca' + case['source_url'],
                'current_output': current or '',
                'prompt_args': case['prompt_args'],
                'parse_args': case['parse_args'],
                'transcript': case['transcript'],
            },
            'metadata': {'task': task, 'tier': case['tier'], 'bucket': case['bucket'], 'case_id': case['id']},
            'assert': asserts,
        })
    return tests

def _links_requested(case: dict) -> bool:
    if case['task'] == 'section':
        return section_links_requested(case['prompt_args']['wordcount'])
    return True


##########################
# Deterministic checks
##########################

def _as_text(output) -> str:
    # promptfoo passes responses from JSON mode already parsed
    return output if isinstance(output, str) else json.dumps(output)

def _result(checks: list[tuple[str, bool]]) -> dict:
    failures = [name for name, ok in checks if not ok]
    return {
        'pass': not failures,
        'score': (len(checks) - len(failures)) / len(checks) if checks else 1,
        'reason': ('Failed: ' + '; '.join(failures)) if failures else 'All checks passed',
    }

def check_valid(output: str, context: dict) -> dict:
    """Would production accept this response? (Production retries up to twice if not.)"""
    output = _as_text(output)
    v = context['vars']
    _, parse = TASKS[v['task']]
    try:
        parse(output, v['transcript'], **v['parse_args'])
    except Exception as e:
        return {'pass': False, 'score': 0, 'reason': f"{type(e).__name__}: {e}"[:500]}
    return {'pass': True, 'score': 1, 'reason': 'Passes production validation'}

def _words(text: str) -> int:
    return len(strip_markdown_links(text).replace('**', '').split())

# Word limits get this much slack before they count as a failure
SLACK = 1.1

def _word_limit(label: str, text: str, max_words: int, min_words: int = 0) -> tuple[str, bool]:
    n = _words(text)
    return (f"{label} is {n} words (asked for {f'{min_words}-' if min_words else '≤'}{max_words})",
            min_words / SLACK <= n <= max_words * SLACK)

def _link_checks(text: str) -> list[tuple[str, bool]]:
    links = markdown_links(text)
    urls = [url for _, url in links]
    long_links = [t for t, _ in links if len(t.split()) > 4]
    return [
        (f"{len(urls) - len(set(urls))} URLs linked more than once", len(urls) == len(set(urls))),
        (f"link text over 4 words: {long_links}", not long_links),
    ]

def check_instructions(output: str, context: dict) -> dict:
    """Does the response follow the constraints the prompt asks for, beyond what production
    validates? Score is the fraction of checks passed."""
    output = _as_text(output).strip()
    v = context['vars']
    task, args = v['task'], v['prompt_args']
    checks = []

    if task in ('bill_party', 'adjournment', 'subheds'):
        try:
            data = load_json_response(output)
        except ValueError:
            return {'pass': False, 'score': 0, 'reason': 'Invalid JSON'}

    try:
        if task == 'bill_overview':
            checks.append(_word_limit('summary', output, 45, 15))
            checks.append(('no Markdown formatting', not re.search(r'\*\*|^#|\]\(', output, re.M)))

        elif task == 'bill_party':
            bullets = data['bullet_points']
            checks.append((f"{len(bullets)} bullet points (asked for 1-4)", 1 <= len(bullets) <= 4))
            for i, b in enumerate(bullets, 1):
                checks.append(_word_limit(f"bullet {i} headline", b['headline'], 6, 2))
                checks.append(_word_limit(f"bullet {i} summary", b['summary'], 40, 8))

        elif task == 'section':
            checks.append(_word_limit('summary', output, section_word_limit(args['wordcount'])))
            if args['bill_debated']:
                checks.append(('begins with "The bill"', output.startswith('The bill')))
            if section_links_requested(args['wordcount']):
                checks.extend(_link_checks(output))
            else:
                checks.append(('no links (not requested)', not markdown_links(output)))

        elif task == 'adjournment':
            checks.append(_word_limit('summary', data['summary'], 50))
            checks.append(_word_limit('topic', data['topic'], 6, 2))

        elif task == 'qp':
            checks.append(_word_limit('summary', output, qp_word_limit(args['party_wordcount'])))
            checks.append(('begins with "The **Party**"', bool(re.match(r'The \*\*[^*]+\*\*', output))))
            checks.append(('single paragraph', '\n' not in output))
            checks.extend(_link_checks(output))

        elif task == 'subheds':
            for item in data['headings']:
                checks.append(_word_limit(f"topic {item['topic']!r}", item['topic'], 6, 1))
            # Every statement by an MP should get a heading (statements without a party are
            # generally the Speaker)
            mp_urls = set(re.findall(r'URL: (/\S+)\nParty:', v['transcript']))
            covered = mp_urls & {item.get('url') for item in data['headings']}
            checks.append((f"headings for {len(covered)} of {len(mp_urls)} MPs' statements",
                           len(covered) >= 0.9 * len(mp_urls)))
    except (KeyError, TypeError, AttributeError) as e:
        return {'pass': False, 'score': 0, 'reason': f"Unexpected structure: {type(e).__name__}: {e}"}

    return _result(checks)


##########################
# Transforms for the LLM judges
##########################

def readable_output(output: str, context: dict) -> str:
    """The response as a reader would see it (JSON responses rendered as text)."""
    output = _as_text(output)
    task = context['vars']['task']
    try:
        if task == 'bill_party':
            return "\n".join(f"- {b['headline']}: {b['summary']}"
                             for b in load_json_response(output)['bullet_points'])
        if task == 'adjournment':
            data = load_json_response(output)
            return f"{data['topic']}\n\n{data['summary']}"
        if task == 'subheds':
            return "\n".join(f"- {item['topic']}" for item in load_json_response(output)['headings'])
    except (ValueError, KeyError, TypeError):
        pass
    return strip_markdown_links(output)

def _link_targets(transcript: str) -> dict[str, tuple[str, str]]:
    """Returns {url: (speaker, text)} for the statement and paragraph URLs in a transcript."""
    targets = {}
    for block in transcript.split('\n\n----\n\n'):
        header, _, body = block.partition('\n\n\n')
        fields = dict(line.split(': ', 1) for line in header.splitlines() if ': ' in line)
        speaker = fields.get('Name', '?')
        if fields.get('Party'):
            speaker += f" ({fields['Party']})"
        if fields.get('Title'):
            speaker += f", {fields['Title']}"
        if 'URL' in fields:
            targets[fields['URL']] = (speaker, re.sub(r'\[/\S+\] ', '', body))
        paragraphs = body.split('\n\n')
        for i, para in enumerate(paragraphs):
            m = re.match(r'\[(/\S+)\] ', para)
            if m:
                # The paragraph where the discussion begins, and what follows
                following = re.sub(r'\[/\S+\] ', '', '\n\n'.join(paragraphs[i:i + 3]))
                targets[m.group(1)] = (speaker, following)
    return targets

def link_report(output: str, context: dict) -> str:
    """The response plus, for each link, the text it links to (for the link-accuracy judge)."""
    output = _as_text(output)
    v = context['vars']
    task = v['task']
    links = []  # (link text, context, url)
    try:
        if task == 'bill_party':
            for b in load_json_response(output)['bullet_points']:
                links.append((b['headline'], b['summary'], b['source_paragraph_url']))
        elif task == 'subheds':
            for item in load_json_response(output)['headings']:
                links.append((item['topic'], '', item['url']))
        else:
            sentences = re.split(r'(?<=[.!?])\s+', output.strip())
            for text, url in markdown_links(output):
                sentence = next((s for s in sentences if f"]({url})" in s), '')
                links.append((text, strip_markdown_links(sentence), url))
    except (ValueError, KeyError, TypeError):
        return f"{output}\n\n(Couldn't extract links: the output isn't in the expected format.)"

    if not links:
        return f"{readable_output(output, context)}\n\nLINKS: none"

    targets = _link_targets(v['transcript'])
    r = f"SUMMARY:\n{readable_output(output, context)}\n\nLINKS:\n"
    for i, (text, ctx, url) in enumerate(links, 1):
        r += f"\n{i}. Link text: \"{text}\"\n"
        if ctx:
            r += f"   In context: \"{ctx}\"\n"
        if url in targets:
            speaker, target = targets[url]
            if len(target) > 1500:
                target = target[:1500] + ' [...]'
            r += f"   Links to a speech by {speaker}:\n   \"\"\"{target}\"\"\"\n"
        else:
            r += f"   Links to: TARGET NOT FOUND ({url})\n"
    return r
