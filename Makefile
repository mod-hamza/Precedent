# On Windows run with mingw32-make (or `make` from Git Bash if installed).
ifeq ($(OS),Windows_NT)
PY ?= .venv/Scripts/python
else
PY ?= .venv/bin/python
endif

.PHONY: setup ingest pipeline stages serve demo snapshot warm eval eval-holdout checks docs test

setup:
	python -m venv .venv
	$(PY) -m pip install -r requirements.txt

ingest:  ## Stage 0: parse, thread, resolve identities
	$(PY) -m backend.ingest

pipeline: ingest  ## all stages over the 560 emails (PRD §16: < 25 min)
	$(PY) -m backend.pipeline

stages:  ## Stages 1-5 only (Stage 0 already done)
	$(PY) -m backend.pipeline

serve:  ## API + built frontend on http://127.0.0.1:8000 (live mode)
	$(PY) -m backend.app

demo:  ## cached run, no network (PRD §16)
	$(PY) -m backend.demo serve

snapshot:  ## freeze the current DB into demo/cached_run.sqlite
	$(PY) -m backend.demo snapshot

warm:  ## pre-answer the suggested questions so demo mode can serve them offline
	$(PY) -m backend.demo warm

eval:  ## dev scorecard -> eval/results/
	$(PY) -m eval.run --split dev

eval-holdout:  ## the ONE frozen holdout run; tag the commit first
	$(PY) -m eval.run --split holdout

checks:  ## fast dev-split stage checks
	$(PY) -m eval.stage_checks
	$(PY) -m eval.ledger_checks

docs:  ## regenerate docs/API.md from live responses
	$(PY) tools/gen_api_docs.py

test:
	$(PY) -m pytest -q tests
