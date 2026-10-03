# Summary prompt evals

Compares LLMs (and prompt changes) on the prompts behind the debate and bill summaries,
using [promptfoo](https://www.promptfoo.dev/). You get a grid of outputs (test cases ×
models) to read, plus automated scores.

- The prompts come straight from the app's own code: the templates in
  `parliament/summaries/prompt_templates/`, rendered by `parliament/summaries/prompts.py`.
  If you edit a prompt, the next eval run uses the new version.
- Test cases are real LLM calls from recent sittings and bill debates. They're exported
  from the database to `evalset.json`, and each includes the summary currently on the site.

## Running

```bash
# 1. Export the test cases (48 by default, spread across the 6 kinds of LLM call)
docker compose exec -T op python manage.py export_summary_evalset

# 2. One-time setup, in this directory. This installs promptfoo and the Claude Agent SDK
#    (pinned in package.json; the SDK is for the judge, see below), creates .venv with
#    Jinja2 for the Python hooks, and copies .env.example to .env.
cd parliament/summaries/eval
npm install
#    Then put your OpenRouter key (same as settings.OPENROUTER_API_KEY) in .env.

# 3. Run the eval. promptfoo reads .env automatically when run from this directory.
npx promptfoo eval

# 4. Look at the results
npx promptfoo view
```

Useful options:

- `--filter-providers 'sonnet|gemini-3.8'`: run only some of the models.
- `--filter-metadata task=qp`: run only one kind of call. The tasks are `bill_overview`,
  `bill_party`, `section`, `adjournment`, `qp` and `subheds`.
- `--filter-metadata tier=quick` (or `tier=thinking`): run only the calls that production
  sends to that model tier.
- `--repeat 3 --no-cache`: run each case three times, to measure how often a model passes
  rather than a single pass/fail. Combine it with `SUMMARY_EVAL_JUDGES=0` to skip the
  (comparatively expensive) LLM judges on repeats.

## Trying a prompt change

Edit the template in `prompt_templates/` and run the eval again. Every run is saved, so
`promptfoo view` can switch between the before and after runs.

To see both versions side by side in one grid, copy the template (e.g. `qp.j2` to
`qp_v2.j2`) and add a second prompt function to `promptfoo_eval.py` that renders the copy
for that task. Then list the new function under `prompts` in `promptfooconfig.yaml`, and
use `--filter-metadata task=qp` so the other tasks don't run against it.
