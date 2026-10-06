# Precedent

"Why did we decide that?" Answered in seconds, with receipts. See `PRD.md` for the product spec and
`STORY_BIBLE.md` for the synthetic corpus.

## Setup

```bash
py -3.11 -m venv .venv            # or python3.11 -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
cp .env.example .env              # add OPENAI_COMPAT_API_KEY (hackathon Model Studio key)
```

Models (OpenAI-compatible, Alibaba Cloud Model Studio): FAST `qwen3.8-flash` (reasoning off), CORE `qwen3.8-max`,
REASON `deepseek-v4-pro`. Override any role with `PRECEDENT_<ROLE>_MODEL`. Embeddings run locally
(sentence-transformers) because the plan has no embeddings endpoint.

## Run

| Step | Command |
| --- | --- |
| Stage 0: parse, thread, identities | `python -m backend.ingest [paths...] [--no-llm]` |
| LLM smoke test (one call per role) | `python -m backend.llm` |
| Tests | `python -m pytest -q tests` |

`mingw32-make ingest` / `mingw32-make test` do the same on Windows.

## Layout

```
backend/   config.py db.py (schema) llm.py cache.py embed.py models.py
           ingest/  parse.py thread.py identity.py
           prompts/ extract.md
tests/     test_stage0.py test_llm.py
corpus/    emails/*.eml (input)   json/ (generation sources, not read by the pipeline)
eval_private/  ground truth + manifest: only eval/ may read these
tools/     corpus generation scripts
```

The pipeline (`backend/`) never reads `eval_private/`; a test enforces it.
