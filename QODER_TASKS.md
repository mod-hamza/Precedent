# Qoder task list

Work for Qoder in the final hours. The backend, pipeline, eval harness and demo snapshot are done and pushed; these
tasks build everything the user sees on top of the API, plus the remaining PRD items. Each task is self-contained:
paste it into Qoder with this file and `PRD.md` open. Run the backend first:

```bash
.venv/Scripts/python -m backend.demo serve      # offline demo data on http://127.0.0.1:8000
```

Qoder CLI (optional, to run tasks from a terminal): install it per Qoder's docs, run its login once yourself (it
opens your Qoder account in the browser), then work from the repo root so it can read `PRD.md`, `docs/API.md` and
this file. The IDE works just as well.

API reference with real example payloads: `docs/API.md`. All endpoints are under `/api`, JSON, no auth. Every GET
accepts `?redact=1` (PII masking).

---

## T1. Frontend scaffold (Vite + React + TypeScript + Tailwind)  ~30 min

Create `frontend/` with Vite + React + TS + Tailwind 4. Dev server proxies `/api` to `http://127.0.0.1:8000`;
`npm run build` outputs `frontend/dist`, which FastAPI already serves at `/` (see `backend/app.py`, bottom).

- Typed API client in `frontend/src/api.ts` for every endpoint in `docs/API.md` (types mirror the JSON).
- App shell: left rail (Ingest · Timeline · Ask · Conflicts · Scorecard), top bar with a **Demo mode** toggle
  (`POST /api/demo/load {"enabled": true|false}`), a **PII redaction** toggle (adds `?redact=1` to every GET), and a
  live counter strip from `GET /api/stats`: `560 emails · 198 candidate threads · N decisions`.
- Scope banner (PRD §10.5): "Precedent only sees the mail it was given; decisions made by phone or in person are missing."
- Design direction (PRD §9): calm editorial "case file": warm off-white background, dark ink, a serif for decision
  text (e.g. Source Serif / Newsreader), a clean sans for UI (e.g. Inter), one accent colour per status:
  Active green, Superseded grey + strikethrough title, Amended amber, Contested red split badge. Chips: `Implicit`,
  `Cross-thread`, `Authority?`. Desktop-first at 1440x900.
- Keyboard: `/` focuses Ask, `Esc` closes drawers/modals.
- Shared states for every screen: empty, loading (skeletons), error with retry, partial result.

## T2. Ingest screen  ~40 min

- Drag-and-drop zone (.eml files, a .zip, or an .mbox) -> `POST /api/ingest` (multipart field `files`), and a
  **Load demo corpus** button -> `POST /api/ingest/corpus`. Both return `run_id`. (Both need demo mode OFF.)
- Subscribe to `GET /api/runs/{run_id}/events` (Server-Sent Events). Event types: `stage_start`, `progress`
  (`stage`, `done`, `total`), `stage_done` (stage stats), `decision_found` (`decision_id`, `text`, `date`, `status`),
  `run_done`, `error`.
- Pipeline stepper: Parse -> Triage -> Extract -> Cluster -> Reconcile -> Index, each with a progress bar.
- Live feed of "Decision found" cards sliding in.
- Funnel readout from `GET /api/stats`: emails -> candidate threads -> records -> decisions -> evidence verified %.
- In demo mode, show the funnel from `/api/stats` directly (the run already happened) with a "Run live" note.

## T3. Timeline + Decision drawer  ~60 min

- `GET /api/graph` -> one horizontal swimlane per `lanes[]` (topic), nodes placed by `decided_at`, curved arrows
  for `edges[]` labelled with `kind` (supersedes / amends / refines). Superseded nodes dimmed. Filter chips by status
  and type. Static SVG is fine (PRD cut line 4: no animation needed).
- Clicking a node opens the **Decision Drawer** (right, 480px) from `GET /api/decisions/{id}`: serif title, status
  badge, decided-by + date, rationale, alternatives, **History chain** (vertical stepper from `history[]` + `edges[]`,
  each item clickable), topic current state, **Evidence list** (sender, date, role chip, quote; forwarded evidence
  shows `original_author` / `original_date`), "Open email" -> modal.
- Footer: `confidence_label.label` with a tooltip showing `confidence_label.why`; authority flag note if present;
  **Dispute this decision** button -> `POST /api/decisions/{id}/dispute {"note": "..."}`.
- Email modal: `GET /api/emails/{message_id}` (URL-encode the id; it contains `<`, `@`, `>`); show headers, new text
  with the quote highlighted, collapsible quoted history and forwarded block, and the thread list.

## T4. Ask screen  ~50 min

- Large input, 6 suggested questions from `demo/suggested_questions.json`; `POST /api/ask {"question": "..."}`.
- Answer panel renders `answer_md`; replace `[^n]` markers with superscript citation chips; hover a chip -> popover
  with the quote, sender and date; click -> email modal with the quote highlighted.
- Side panel "Decisions used" from `decisions[]` with status badges (click -> drawer).
- `status == "no_decision"`: distinct "No decision found" state with the **Closest discussions** list (`closest[]`).
- `status == "contested"`: two columns, Version A | Version B (pull sides from `GET /api/conflicts` for the
  decision ids in the answer).
- Show the deterministic `confidence` label (not `model_confidence`) and `caveats[]`. Show `latency_ms` subtly.
- A 503 means demo mode is offline and the question is not cached: show that message, not a crash.

## T5. Conflicts screen  ~25 min

- `GET /api/conflicts`: one card per conflict with a split view; each side shows claimant, claim and evidence quotes.
- Note on every card: "Precedent will not choose a side; resolve this with the people involved."

## T6. Scorecard screen  ~40 min

- `GET /api/eval/latest`: metric tiles (recall, precision, near-decision false positives, supersession accuracy,
  conflicts, evidence support, Q&A accuracy, no-decision correctness, latency p50, quote validity, pipeline minutes)
  each against `targets`; a Dev / Holdout toggle over `splits`.
- Table of GT decisions from `splits[s].decisions_table` with Hit / Partial / Miss and a drill-down showing GT text vs
  predicted text and statuses. Q&A table from `splits[s].qa`.
- A clear banner with `banner` ("Synthetic corpus; ground truth hidden from the pipeline.").
- Metrics below target are shown honestly (no hiding); that is part of the Responsible-AI story.

## T7. Polish and states  ~30 min

- Check every screen at 1440x900 in both demo and live mode; empty/loading/error/partial/no-decision states.
- Lighthouse-style pass for contrast and focus rings; make the rail keyboard-navigable.

## T8. Screenshots and video  (humans + Qoder)  ~40 min

- With demo mode on, capture the 8 frames from PRD §12 into `demo/screenshots/` and record the ~90 s video
  (storyline in PRD §12).

## T9. Stopwatch test and submission  ~40 min

- Stopwatch test (PRD §11): time a manual search in a raw mailbox viewer for 5 questions vs Precedent's p50.
- Fill in `SUBMISSION.md` (draft provided): team, screenshots, stopwatch numbers, video link.

## T10. Optional if time remains

- Enron 200-email sanity check (PRD §11; check licensing first): run `python -m backend.ingest <dir>` then
  `python -m backend.pipeline`, hand-verify 3 decisions, write a short qualitative note.
- Frontend tests (Vitest) for the citation-chip renderer and the SSE client.
