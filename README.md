# Precedent

"Why did we decide that?" Answered in seconds, with receipts. See `PRD.md` for the product spec,
`STORY_BIBLE.md` for the synthetic corpus, `docs/API.md` for the API, `QODER_TASKS.md` for the frontend plan.

## Setup

```bash
py -3.11 -m venv .venv            # or python3.11 -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
cp .env.example .env              # add OPENAI_COMPAT_API_KEY (hackathon Model Studio key)
```

Models (OpenAI-compatible, Alibaba Cloud Model Studio): FAST `qwen3.8-flash` (reasoning off), CORE `qwen3.8-max`,
REASON / JUDGE `deepseek-v4-pro`, ANSWER `qwen3.8-max` (reasoning off). Override any role with
`PRECEDENT_<ROLE>_MODEL`. Embeddings run locally (sentence-transformers) because the plan has no embeddings endpoint.

## Run

`mingw32-make <target>` on Windows, `make <target>` elsewhere (or run the Python commands directly).

| Target | What it does |
| --- | --- |
| `pipeline` | Stage 0 ingest + Stages 1-5 over `corpus/emails` (~12 min, results cached) |
| `serve` | API (+ built frontend) on http://127.0.0.1:8000 |
| `demo` | load `demo/cached_run.sqlite` and serve offline (no network, no model calls) |
| `eval` / `eval-holdout` | scorecard -> `eval/results/` (served at `/api/eval/latest`) |
| `checks` | fast dev-split checks while tuning |
| `snapshot` / `warm` | freeze the current DB into the demo snapshot / pre-answer the suggested questions |
| `docs` | regenerate `docs/API.md` from live responses |
| `test` | unit tests + integrity of the latest run (100% verbatim quotes) |

Single question from the shell: `python -m backend.ask "Why did we switch payment providers?"`

## Pipeline

```
.eml/.mbox -> 0 parse/thread/identity -> 1 triage (FAST) -> 2 extract (CORE) + quote verifier (code)
           -> 3 cluster (REASON) -> 4 reconcile (REASON) -> 5 index (FTS5 + embeddings) -> 6 ask (ANSWER)
```

Every model call returns JSON validated by Pydantic (one repair retry) and is cached on
sha256(model + prompt + schema); token usage per stage is logged in `llm_calls`. Every quote stored or shown is a
verbatim substring of its email (enforced in `backend/pipeline/verify.py`, proven by `tests/test_run_integrity.py`).

## Layout

```
backend/   app.py (API) config.py db.py llm.py cache.py embed.py models.py render.py (PII) demo.py ask.py
           ingest/   parse.py thread.py identity.py
           pipeline/ context.py triage.py extract.py verify.py cluster.py reconcile.py index.py ask.py run.py
           prompts/  triage.md extract.md cluster.md reconcile.md classify.md answer.md
eval/      run.py match.py judge.py report.py stage_checks.py ledger_checks.py tune_cluster.py; results/
tests/     unit tests + run integrity
corpus/    emails/*.eml (input)   json/ (generation sources, never read by the pipeline)
eval_private/  ground truth + manifest: only eval/ reads these
demo/      cached_run.sqlite, suggested_questions.json, screenshots/
docs/      API.md
tools/     corpus generation, API doc generator
```

The pipeline (`backend/`) never reads `eval_private/`; a test enforces it.
