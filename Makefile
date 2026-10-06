# On Windows run with mingw32-make (or `make` from Git Bash if installed).
ifeq ($(OS),Windows_NT)
PY ?= .venv/Scripts/python
else
PY ?= .venv/bin/python
endif

.PHONY: setup ingest test

setup:
	python -m venv .venv
	$(PY) -m pip install -r requirements.txt

ingest:  ## Stage 0: parse, thread, resolve identities
	$(PY) -m backend.ingest

test:
	$(PY) -m pytest -q tests
