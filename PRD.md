# PRD: Precedent (working name), v1.0

> *"Why did we decide that?" Answered in seconds, with receipts.*

**Audience:** Claude Opus (lead builder). **Build window:** 24 hours, 3 humans + AI agents.
**Companion doc:** `STORY_BIBLE.md` defines the synthetic corpus (560 emails, 40 planted decisions) and the hidden answer key. **The pipeline must never read the ground truth.** Only `eval/` may.

---

## 1. Summary

**One-liner:** We help small teams that run on email solve lost and re-argued decisions through a decision-tracking system and an AI that extracts, links and cites every decision, cutting the time to answer "why did we choose this?" from minutes of inbox searching to seconds, with [X]% recall and [Y]% evidence accuracy on a 560-email benchmark with known ground truth.

**What it is:** Upload a mailbox (`.eml` / `.mbox`). Precedent builds a **decision ledger**: every business decision with its rationale, alternatives, decider, status (active / superseded / amended / contested), and quoted evidence from specific emails. Ask questions in plain language and get cited answers, including an honest "no decision found."

**What makes it more than "chat with your inbox":**
1. Decisions are modeled as a **lifecycle**: proposals → decisions → amendments → reversals, linked into a graph.
2. **Implicit decisions** are detected ("ok saturday then" + 👍).
3. **Cross-thread stitching**: a decision spread over threads and meeting recaps becomes one record.
4. **Contested decisions** show both versions rather than silently picking one.
5. **Authority check**: flags decisions made by someone without apparent authority.
6. **Programmatic quote verification**: every cited quote is checked as a verbatim substring of the cited email, or it is dropped. No hallucinated evidence reaches the UI.
7. It ships with a **benchmark and a scorecard**, so every claim in the submission is measured.

---

## 2. Users and scenarios

| Persona | Pain | Scenario |
|---|---|---|
| **Founder/CEO** | Decisions get re-litigated; "didn't we already settle this?" | Asks "Did we ever decide on a free tier?" and gets "No. Closest: Chloe's proposal on Mar 4, never approved." |
| **New hire** (Elena) | Joined mid-flight, no history | Asks "Why is the DB still on NimbusHost?" and gets the full reasoning chain. |
| **Finance lead** | Needs the *current* approved number | Asks "What's the Redline renewal discount?" and gets "10% (Marta, Feb 11). The 15% offer was unauthorized." |

**Primary demo target:** a small team whose whole decision history lives in email.

---

## 3. Goals and non-goals

**Goals (must ship):** G1 ingest + parse 560 emails reliably · G2 decision ledger with evidence · G3 lifecycle graph (supersede/amend/contest) · G4 cited Q&A with refusal · G5 polished UI covering ingest → timeline → ask → conflict → eval · G6 eval scorecard on the holdout · G7 cached demo mode.

**Non-goals:** live Gmail/Outlook OAuth (roadmap) · WhatsApp/Slack (roadmap; the connector interface exists) · multi-tenant auth · attachments beyond filename + plain-text · mobile layout · fine-tuning · production-grade scale (target: ≤ 5k emails).

---

## 4. Success metrics (targets for the HOLDOUT split)

| Metric | Target | Definition |
|---|---|---|
| Decision recall | ≥ 85% | matched GT decisions / GT decisions |
| Decision precision | ≥ 85% | predicted decisions matched to a GT decision / predicted decisions |
| False positives on near-decisions | ≤ 2 of 10 | predicted decisions that correspond to an N-item |
| Supersession-link accuracy | ≥ 80% | GT edges recovered with correct direction |
| Conflict detection | ≥ 2 of 3 | GT conflicts surfaced with `status=contested` and both versions present |
| Quote validity | 100% | quotes that are verbatim substrings (enforced in code) |
| Evidence support | ≥ 90% | cited emails ⊂ GT evidence set for the matched decision (LLM-judge + human spot-check of 20) |
| Q&A accuracy | ≥ 85% of 30 | rubric-judged, see §11 |
| "No decision" correctness | 5/5 | N-questions correctly refused |
| Answer latency | p50 < 8 s | after index built |
| Full pipeline wall-clock | < 25 min / 560 emails | with parallelism ≥ 8 |

Report dev and holdout separately. If a number is below target, report it honestly (that is a feature for the Responsible-AI score).

---

## 5. Architecture

```
 .eml/.mbox ──► [0 Parse+Thread+Identity] ──► SQLite
                         │
                 [1 Triage]  (cheap model, per thread, recall-biased)
                         │ candidate threads
                 [2 Extract]  (mid model, per thread → DecisionRecords w/ evidence)
                         │ + [2b Quote Verifier]  (code, no LLM)
                 [3 Cluster]  (embeddings + rules → topic clusters)
                         │
                 [4 Reconcile] (strong model, per cluster → decisions, edges, conflicts, current state)
                         │
                 [5 Index]  FTS5 + embeddings over decisions and email passages
                         │
        FastAPI ◄──── [6 Ask] retrieve → answer → verify citations → respond
           │
        React UI (Timeline · Ask · Conflicts · Eval)   +   SSE progress stream
```

**Stack (keep it boring):** Python 3.11, FastAPI, SQLite (WAL, FTS5), `numpy` cosine similarity over stored embeddings (≤ 20k vectors; no vector DB), Pydantic v2 for every LLM output schema, `asyncio` + semaphore for parallel LLM calls. Frontend: Vite + React + TypeScript + Tailwind, served statically by FastAPI. One `make demo` starts everything.

**Model roles (configurable via env; abstract behind `llm.py`):**
| Role | Used for | Default |
|---|---|---|
| `FAST` | Triage, question classification | `claude-haiku-4-5-20251001` |
| `CORE` | Extraction, answers | `claude-sonnet-5-5` |
| `REASON` | Reconciliation, eval judging | `claude-opus-5-5` |
| `EMBED` | Embeddings | any available embedding endpoint behind an adapter; fallback `sentence-transformers` locally |

Rules: temperature 0; JSON output validated by Pydantic with one automatic repair retry; cache every LLM call on `sha256(model + prompt + schema)` in SQLite (re-runs are free and demos are reproducible); log token counts and cost per stage to the `runs` table.

**Isolation requirement:** the extraction/Q&A pipeline has *no* import path to `eval_private/`. Eval is a separate CLI (`python -m eval.run`).

---

## 6. Data model (SQLite)

```sql
CREATE TABLE emails(
  id INTEGER PRIMARY KEY,
  message_id TEXT UNIQUE NOT NULL,
  thread_id TEXT, in_reply_to TEXT, refs TEXT,
  from_person_id INTEGER, from_addr TEXT, from_name TEXT,
  to_addrs TEXT, cc_addrs TEXT,            -- JSON arrays
  sent_at TEXT NOT NULL,                   -- ISO-8601 UTC
  sent_tz TEXT,                            -- original offset
  subject TEXT,
  new_text TEXT,        -- the sender's own words only
  quoted_text TEXT,     -- stripped reply chains
  fwd_text TEXT,        -- forwarded content (with parsed original author/date in fwd_meta)
  fwd_meta TEXT,
  body_raw TEXT,
  attachment_names TEXT,
  source_file TEXT
);
CREATE TABLE people(id INTEGER PRIMARY KEY, canonical_name TEXT, role_guess TEXT, org TEXT, is_internal INT);
CREATE TABLE identities(id INTEGER PRIMARY KEY, person_id INT, kind TEXT, value TEXT, UNIQUE(kind,value)); -- kind: email|display_name
CREATE TABLE threads(thread_id TEXT PRIMARY KEY, subject_norm TEXT, first_at TEXT, last_at TEXT, n_msgs INT, participants TEXT);
CREATE TABLE triage(thread_id TEXT, message_id TEXT, signal TEXT, note TEXT, PRIMARY KEY(thread_id,message_id));
CREATE TABLE records(                      -- raw extraction output (pre-reconcile)
  record_id TEXT PRIMARY KEY, thread_id TEXT, topic_label TEXT, decision_text TEXT,
  stance TEXT, decision_type TEXT, decided_by TEXT, decision_date TEXT,
  rationale TEXT, alternatives TEXT, conditions TEXT, overrides_hint TEXT,
  authority_note TEXT, confidence REAL, embedding BLOB, cluster_id TEXT
);
CREATE TABLE evidence(
  id INTEGER PRIMARY KEY, owner_kind TEXT,  -- 'record'|'decision'|'conflict_side'
  owner_id TEXT, message_id TEXT, quote TEXT, role TEXT, verified INT   -- verified = 1 only if substring check passed
);
CREATE TABLE clusters(cluster_id TEXT PRIMARY KEY, topic TEXT, summary TEXT, current_state TEXT, n_records INT);
CREATE TABLE decisions(
  decision_id TEXT PRIMARY KEY, cluster_id TEXT, canonical_text TEXT, decided_by TEXT, decided_at TEXT,
  rationale TEXT, alternatives TEXT, decision_type TEXT,        -- explicit|implicit
  status TEXT,                                                  -- active|superseded|amended|contested
  authority_flag INT, authority_note TEXT, confidence REAL, embedding BLOB
);
CREATE TABLE decision_edges(src TEXT, dst TEXT, kind TEXT, scope TEXT, aspect TEXT, rationale TEXT);
  -- kind: supersedes|amends|refines ; scope: full|partial ; src is the NEWER decision
CREATE TABLE conflicts(conflict_id TEXT PRIMARY KEY, cluster_id TEXT, topic TEXT, summary TEXT);
CREATE TABLE conflict_sides(conflict_id TEXT, side TEXT, claimant TEXT, claim TEXT);   -- evidence in evidence table
CREATE TABLE passages(id INTEGER PRIMARY KEY, message_id TEXT, text TEXT, embedding BLOB);
CREATE VIRTUAL TABLE passages_fts USING fts5(text, content='passages', content_rowid='id');
CREATE VIRTUAL TABLE decisions_fts USING fts5(canonical_text, rationale, content='decisions');
CREATE TABLE qa_log(id INTEGER PRIMARY KEY, question TEXT, answer_json TEXT, latency_ms INT, created_at TEXT);
CREATE TABLE runs(run_id TEXT, stage TEXT, started_at TEXT, finished_at TEXT, n_in INT, n_out INT, tokens_in INT, tokens_out INT, cost_usd REAL, notes TEXT);
```
Eval tables (`gt_*`, `split`) live in a **separate** database `eval_private/eval.db`.

---

## 7. Pipeline specification

### Stage 0: Parse, thread, identify (no LLM except ambiguous identities)
- Parse with Python `email` (policy=default). Prefer `text/plain`; else HTML → text (`selectolax` or BeautifulSoup), preserving paragraph breaks and list markers. Decode RFC2047 headers and mixed charsets. Dedupe on `Message-ID` (fall back to hash of from+date+subject+first 200 chars).
- **Split `new_text` from `quoted_text` and `fwd_text`.** Detect: lines starting `>`; `On <date>, <name> wrote:` / localized variants (`Am … schrieb`, `El … escribió`); Outlook blocks (`From:/Sent:/To:/Subject:`); `-----Original Message-----`; `---------- Forwarded message ---------`. For forwards, parse the original author/date into `fwd_meta` so evidence from forwarded text is attributed to the **original** author and date, not the forwarder. Strip signatures (`-- `, "Kind regards" block, "Sent from my iPhone"), legal disclaimers, and trailing "Best,\nName".
- **Threading:** build `thread_id` via union-find over `References`/`In-Reply-To`; fallback for broken threads: same normalized subject (strip `Re:/Fwd:/AW:/RE:`), participant overlap ≥ 50%, within 14 days. Keep `n_msgs` and chronological order by `sent_at`.
- **Identity resolution:** (1) exact email; (2) normalized display name (casefold, strip accents/punctuation, token-set ratio ≥ 0.9) within the same domain; (3) remaining ambiguous pairs adjudicated by `FAST` with signatures as context. Output: `people` + `identities`. Infer `role_guess` and `is_internal` from signatures and domains (the pipeline is *not* given the authority matrix; it infers from signatures and behavior, which is itself part of the demo).
- **Acceptance:** 560/560 parsed; ≥ 99% thread-correct on planted threads (eval checks); all quoted-chain text excluded from `new_text` on a 50-email hand check.

### Stage 1: Triage (`FAST`, one call per thread)
Input: the thread's messages in order (`message_id, sender name, date, new_text`, plus short `fwd_text`). Output (Pydantic `TriageResult`):
```json
{"thread_id": "...", "has_candidate": true,
 "messages": [{"message_id": "...", "signal": "none|discussion|proposal|approval|decision|reversal|commitment|question", "note": "≤15 words"}]}
```
**Bias toward recall.** `has_candidate=true` if any message has `proposal|approval|decision|reversal` or if a `question` is followed by an affirmative reply. Threads with `has_candidate=false` stop here (cost control and a visible "filtered X% as noise" stat for the UI). *Acceptance on dev:* ≥ 98% of GT decision threads pass the triage.

### Stage 2: Extraction (`CORE`, one call per candidate thread)
Input: full thread (as above) + the people directory + the list of other threads sharing ≥ 2 participants within ±14 days (subject lines only, as cross-thread hints). Output: `ExtractionResult { records: DecisionRecord[] }`.

```json
DecisionRecord = {
  "topic_label": "short noun phrase, e.g. 'Payment provider'",
  "decision_text": "one sentence, imperative or past tense, self-contained",
  "stance": "final | tentative | proposed | conditional | retracted",
  "decision_type": "explicit | implicit",
  "decided_by": ["Person Name", ...],          // who has the authority or whose agreement closed it
  "decision_date": "YYYY-MM-DD",               // date of the message that closed it
  "rationale": "string|null", "alternatives": ["..."],
  "conditions": "string|null",                 // for conditional stance
  "overrides_hint": "string|null",             // 'changes the earlier plan to X', if language says so
  "authority_note": "string|null",             // e.g. 'sales lead offered 15%; no sign-off in thread'
  "evidence": [{"message_id": "...", "quote": "verbatim, ≤40 words", "role": "proposal|discussion|objection|approval|confirmation|reversal|recap"}],
  "confidence": 0.0
}
```

**Extraction system prompt (use verbatim as the baseline):**
```
You extract business DECISIONS from an email thread for a decision ledger.

A DECISION is a commitment to a course of action about money, scope, people, customers, vendors, policy, or an external commitment, that was settled by someone with apparent authority or by clear agreement. It can be informal ("ok saturday then", "fine", "go with X", a thumbs-up to a clear proposal).

NOT decisions (never output as stance=final): questions, hypotheticals ("we could…"), brainstorms, proposals nobody approved (stance=proposed), conditional plans whose condition is unmet (stance=conditional), retracted statements (stance=retracted), assigning yourself or someone a task ("I'll draft it"), deferrals ("let's revisit later"), polite non-answers ("interesting, not now"), trivial logistics (lunch, meeting rooms, moving a standup).

RULES
1. Use only each message's NEW text. Quoted history is context only; never treat a quoted old statement as a new decision. For forwarded text, attribute it to the original author and original date.
2. For every record, cite 1-5 evidence quotes copied EXACTLY (character for character) from a single message's new text or forwarded text. Include the decisive message plus rationale/objection messages.
3. decision_date = the date of the decisive message, not the proposal.
4. decided_by = the person whose words or approval actually closed it. If the closer appears to lack authority for this kind of decision (e.g., a salesperson offering a large discount, with no approval in the thread), set authority_note.
5. If a message says it changes or cancels an earlier plan, set overrides_hint.
6. Do not merge separate decisions. Do not invent rationale; null if absent.
7. If nothing in the thread qualifies, return {"records": []}.
8. Confidence: 0.9+ only for explicit, unambiguous closure; 0.5-0.7 for implicit.
Return JSON only, matching the schema.
```

**2b Quote verifier (code):** normalize (NFKC, collapse whitespace, normalize quotes/dashes, casefold for comparison) and require the quote to be a contiguous substring of the cited message's `new_text` ∪ `fwd_text`. If it fails: try a fuzzy re-anchor (rapidfuzz partial ratio ≥ 95 → snap to the true substring); else mark `verified=0` and drop it from user-visible evidence. A record with zero verified evidence is discarded. Count `quotes_total`, `quotes_snapped`, `quotes_dropped` for the stats panel.

### Stage 3: Cluster
Embed `topic_label + decision_text`. Agglomerative clustering with cosine threshold ~0.72 (tune on dev), constrained so records link only if they share ≥ 1 participant OR cosine ≥ 0.85. Also merge clusters when one record's `overrides_hint` text matches another's decision_text (cosine ≥ 0.65). Output `clusters`. Singleton clusters are valid. *Never* cluster across totally unrelated topics just to reach a target count.

### Stage 4: Reconcile (`REASON`, one call per cluster with ≥ 2 records or any `conditional/proposed` record)
Input: all records in the cluster, chronologically, with their verified evidence, plus the full text of each cited email (new_text only) and the people directory. Output `ReconcileResult`:
```json
{
 "cluster_topic": "...",
 "decisions": [{"decision_id_temp": "d1", "canonical_text": "...", "decided_by": [...], "decided_at": "YYYY-MM-DD",
                "rationale": "...", "alternatives": [...], "decision_type": "explicit|implicit",
                "status": "active|superseded|amended|contested",
                "authority_flag": false, "authority_note": null,
                "merged_record_ids": ["r1","r4"], "confidence": 0.0,
                "evidence": [{"message_id":"...","quote":"...","role":"..."}]}],
 "edges": [{"src":"d2","dst":"d1","kind":"supersedes|amends|refines","scope":"full|partial","aspect":"what changed","rationale":"..."}],
 "conflicts": [{"topic":"...","summary":"...","sides":[{"claimant":"Name","claim":"...","evidence":[...]}]}],
 "current_state": "2-3 sentence plain-language statement of where things stand now, citing dates",
 "non_decisions": [{"record_ids":["r7"], "reason":"proposal never approved"}]
}
```
**Reconcile prompt rules (core):**
1. Merge records describing the same decision across threads into one; take the date of the decisive closure.
2. A later decision that replaces an earlier one `supersedes` it (earlier → `superseded`). A later decision that changes one aspect (timing, scope, amount) `amends` it (earlier → `amended`, with `aspect`). `refines` fills in details without reversing.
3. `contested` only when **two or more people state incompatible versions of what was agreed** and no later message resolves it. Present each side with its own evidence. Do NOT choose a winner. Do not flag differing numbers that are explained innocently (net vs gross).
4. A `proposed`/`conditional`/`retracted` record never becomes a decision. List it in `non_decisions`. If a conditional's condition is never shown to be met, it stays conditional.
5. Set `authority_flag` when the closer lacked apparent authority and no one with authority approved before external communication; if later approved or reversed by someone with authority, say so.
6. Keep every evidence quote verbatim from the inputs. Do not add new quotes from memory.
7. `current_state` must be consistent with the final statuses.

After the call: re-run the quote verifier on all evidence; assign stable IDs `DEC-0001…` ordered by `decided_at`; write `decisions`, `decision_edges`, `conflicts`, `conflict_sides`, `evidence`; update `clusters.current_state`.

**Acceptance (dev):** every status in the dev GT recovered; the D38/D39 conflict clusters yield `contested` with ≥ 2 sides.

### Stage 5: Index
- `passages`: split each `new_text` into ≤ 120-word passages (keep message_id, sender, date); embed + FTS5.
- Embed `canonical_text + rationale` for each decision; FTS5 on text + rationale.

### Stage 6: Ask
Steps:
1. **Classify** (`FAST`) → `{type: current_state|why|history|who|existence|as_of|other, entities: [...], as_of_date: null|date}`.
2. **Retrieve:** hybrid (BM25 + cosine, reciprocal rank fusion) over `decisions` (top 8) and `passages` (top 12). Expand each hit decision to its full edge chain (ancestors + descendants), its cluster's `current_state`, and any conflict.
3. **Answer** (`CORE`): context is the retrieved decisions (with ids, status, chain, evidence quotes with message ids) and passages. Output `Answer`:
```json
{"status": "found|contested|no_decision|partial",
 "answer_md": "plain markdown with inline [^1] markers",
 "citations": [{"n":1,"message_id":"...","quote":"..."}],
 "decision_ids": ["DEC-0012"],
 "confidence": "high|medium|low", "caveats": ["..."],
 "closest": [{"message_id":"...","why":"..."}]}
```
**Answer prompt rules:** answer only from the provided context; every factual claim carries a citation marker; for `current_state` and `as_of` questions, explicitly trace the chain and state what was superseded; if status is `contested` show both versions, never pick; if no decision exists, say so plainly, set `status=no_decision`, and put the nearest discussions in `closest` with a one-line reason each. Never answer a question from general knowledge.
4. **Verify (code):** every marker has a citation; every citation quote passes the substring check; `decision_ids` exist. On failure: one retry with error feedback; else downgrade confidence to `low` and append a caveat.
5. **Confidence rule (deterministic overlay):** `high` = explicit decision, final stance, ≥ 2 verified quotes from ≥ 2 messages; `medium` = implicit or single source; `low` = verification failures, or `partial`. The UI displays the deterministic value, not the model's.

---

## 8. API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/ingest` (multipart: files, zip, or mbox) | start a run; returns `run_id` |
| GET | `/api/runs/{id}/events` (SSE) | stage progress + streaming discoveries (`decision_found` events with id, text, date, status) |
| GET | `/api/stats` | counts: emails, threads, people, candidates, decisions by status, quote stats, cost, time |
| GET | `/api/decisions?status=&q=&from=&to=&cluster=` | ledger list |
| GET | `/api/decisions/{id}` | full card incl. chain, evidence, authority flag |
| GET | `/api/clusters` / `/api/clusters/{id}` | topic lanes + current state |
| GET | `/api/graph` | nodes + edges for the lifecycle view |
| GET | `/api/conflicts` | contested items with both sides |
| GET | `/api/emails/{message_id}` | the email (new_text, quoted, headers) for the viewer |
| POST | `/api/ask` `{question}` | cited answer |
| GET | `/api/eval/latest` | latest scorecard (read-only, from `eval_private/` results export) |
| POST | `/api/demo/load` | load the cached run (demo mode) |

---

## 9. UI specification

**Design direction:** a calm, editorial "case-file" aesthetic (warm off-white, dark ink, one accent color per status), not a generic dashboard. Typography with character (a serif for decision text, a clean sans for UI). Dark mode optional. Desktop-first at 1440×900 so screenshots look great.

**Global:** left rail (Ingest · Timeline · Ask · Conflicts · Scorecard), a top "Demo mode" toggle, a live counter strip (`560 emails · 87 threads with candidates · 41 decisions`).

**Status badges:** Active (green), Superseded (grey, strikethrough title), Amended (amber), Contested (red split-badge), plus small chips: `Implicit`, `Cross-thread`, `Authority?`.

**Screen 1: Ingest.** Drag-and-drop zone (folder/zip/mbox), "Load demo corpus" button. After upload: a pipeline stepper (Parse → Triage → Extract → Verify → Reconcile → Index) with progress bars, a live feed of "Decision found" cards sliding in, and a funnel readout: *560 emails → 87 candidate threads → 52 records → 41 decisions → 38 verified evidence ratio 100%*. This is the video's opening shot.

**Screen 2: Timeline.** Horizontal swimlane per topic cluster (Payments, Pricing, Infra, Launch, …), nodes positioned by date, edges drawn as curved arrows with labels (`supersedes`, `amends`). Superseded nodes dim. Filter chips by status/type. Clicking a node opens the **Decision Drawer**.

**Decision Drawer (right, 480px):** title (serif), status badge, decided-by + date, rationale, alternatives considered, **History chain** (vertical stepper of this decision's ancestors/descendants, each linking), **Evidence list**: each item shows sender, date, role chip, and the quote; "Open email" opens a modal with the full email and the quote highlighted. Footer: confidence label with a "why this confidence" tooltip.

**Screen 3: Ask.** Large input, 6 suggested questions (taken from the Q&A set), answer panel: answer text with superscript citation chips; hover a chip → quote popover; click → email modal with highlight; side panel "Decisions used" (cards with status badges); `status=no_decision` renders a distinct "No decision found" state with the "Closest discussions" list; `contested` renders two columns, Version A | Version B.

**Screen 4: Conflicts.** Cards per contested topic with a split view; each side shows claimant, claim, evidence, plus the note "Precedent will not choose a side; resolve this with the people involved."

**Screen 5: Scorecard.** Metric tiles (recall, precision, near-decision false positives, supersession accuracy, conflict detection, evidence support, Q&A accuracy), a toggle Dev / Holdout, a table of the 40 GT decisions with Hit / Miss / Partial, and drill-down diffs. A clear banner: "Synthetic corpus; ground truth hidden from the pipeline."

**Required states:** empty, loading (skeletons), error (with retry), partial-result, and no-decision. Keyboard: `/` focuses Ask; `Esc` closes drawers.

---

## 10. Responsible AI (build these, don't just describe them)
1. **Citations or silence:** any claim without a verified quote is dropped.
2. **Calibrated refusal:** `no_decision` is a first-class answer (5 test questions).
3. **Contested ≠ resolved:** never silently pick a side.
4. **Authority flag:** surfaces informal-authority issues without accusing anyone ("no sign-off found in this mailbox").
5. **Scope limits:** a banner stating Precedent only sees the mail it was given; decisions made by phone or in person will be missing.
6. **Privacy:** user-supplied upload only; PII-redaction toggle (mask emails/phone numbers/IBANs in the UI and in outputs; implemented as a regex pass at render time); local-model mode in the roadmap; role-based visibility in the roadmap.
7. **Human-in-the-loop:** "Dispute this decision" button writes feedback to `feedback` table (good enough for the demo).
8. **Honest evaluation:** synthetic data is disclosed; holdout reported; limitations listed (see §13).

---

## 11. Evaluation harness (`eval/`, isolated)

- **Inputs:** `eval_private/ground_truth.json`, `manifest.csv`, Precedent's SQLite output.
- **Decision matching:** for each (predicted, GT) pair with |date diff| ≤ 5 days and embedding cosine ≥ 0.55, ask `REASON` (a *different* prompt and, if possible, a different model snapshot than extraction): "Do these two statements describe the same decision? yes/no/partial". Resolve by max-weight one-to-one matching (Hungarian). *Partial* counts as 0.5 for recall and precision, reported separately.
- **Recall/precision:** per split. **Near-decision FPs:** predicted decision judged to assert an N-item as decided.
- **Supersession accuracy:** for each GT edge (src→dst), both ends matched AND a predicted edge exists with the same direction (kind-level match reported separately: supersedes vs amends).
- **Conflicts:** predicted `contested` decision matched to D38/D39/D40 AND ≥ 2 sides each citing at least one GT evidence message.
- **Evidence support:** for matched decisions, share of cited message_ids in the GT evidence set (strict), plus LLM-judge on the rest ("does this quote support the claim?").
- **Q&A:** run all 30 questions; judge with a rubric: (a) required facts present (b) status correct (found/contested/no_decision) (c) ≥ 1 cited gold message (d) no unsupported claims. Score = 1 if a-d pass, 0.5 if a and b only, else 0. Spot-check 10 judgments by hand.
- **Triage recall** and **quote stats** also reported.
- **Output:** `eval_results.json` (exported read-only for `/api/eval/latest`) and a Markdown table for the submission.
- **Protocol:** tune on dev; freeze prompts/code at hour ~18; **one** holdout run; the number you get is the number you report (log it with a git tag).
- **Latency benchmark:** one teammate does a timed manual search ("why did we switch payment providers?") in a raw `.mbox` viewer; compare it with Precedent's p50. Run it on 5 questions; report medians.
- **Real-data sanity check:** run Stage 0 + Stages 1-4 on a 200-email slice of a public real-world corpus (e.g., Enron). Report *qualitative* results and 3 hand-verified decisions only (no accuracy claims). Check the dataset's current licensing and hosting first.

---

## 12. Demo and submission

**Video storyline (≈ 90 s, screen recording; add voiceover if someone is comfortable):**
1. Ingest: drag in the 560 emails; the funnel and live feed populate (15 s).
2. Timeline: zoom into Payments lane; click D02; show the history chain (PayForge → Ledgerly → delayed → July 6) and evidence from three emails (20 s).
3. Ask: "Why did we switch payment providers?" Cited answer; hover a citation (15 s).
4. Ask: "Did we decide to open a Lisbon office?" → "No decision found," with closest discussions (10 s).
5. Conflicts: first-response SLA, two versions side by side (10 s).
6. Authority flag on the Redline 15% offer (5 s).
7. Scorecard with holdout numbers and a visible "synthetic data" banner (15 s).

**Screenshot sequence:** 8 grouped frames matching the above, captured from hour ~12 using demo mode so they are reproducible.

**Submission document (single HTML or MD):** opens with the one-liner, then the eight required sections: 01 Project Summary · 02 Problem & Users · 03 Solution & Flow · 04 AI, Data & Tools (models per stage, synthetic corpus design, split/holdout, verifier) · 05 Demo Evidence (screens + video) · 06 Business Value (scorecard + stopwatch test) · 07 Risks & Next Steps (limits, controls, roadmap: live Gmail OAuth, WhatsApp export, RBAC, local models) · 08 Team & Ownership.

---

## 13. Known limitations (state them)
Synthetic corpus (LLM-written, different model from the extractor, plus a small human-written slice) · only email · no attachments · decisions made verbally are invisible · authority is inferred from signatures/behavior, not an org chart · English-dominant with light multilingual text · small scale (≤ 5k emails tested).

---

## 14. Work plan (24 h)

| Hours | Opus (core) | GLM (data) | Humans |
|---|---|---|---|
| 0-1 | Repo, schema, `llm.py`, caching, Pydantic models | **Pilot batch (35 emails)** | Approve pilot voices; decide product name |
| 1-4 | Stage 0 parser + threading + identity on the pilot; **M1: 560 emails parsed** when corpus lands | Full generation (210+40 thread emails, 310 filler), assembly script | Human-written slice (30-40 emails); QA 30 samples |
| 4-8 | Stage 1+2+verifier; dev-split run; **M2** | Fix QC failures; produce manifest and GT json | Frontend scaffolding (Qoder): shell, Ingest screen |
| 8-12 | Stage 3+4; **M3: graph + statuses on dev** | Q&A set JSON | Timeline + Drawer screens |
| 12-15 | Stage 5+6, answer verification; **M4** | Support: extra N/trap threads if recall too easy | Ask screen; **start screenshots** |
| 15-18 | Eval harness; tune on dev; **M5** | Spare | Conflicts + Scorecard screens; empty/error states |
| 18 | **FREEZE prompts and code. Tag.** | | |
| 18-20 | One holdout run → numbers; demo-mode cache | | Re-shoot screenshots and record the video |
| 20-23 | Bug-fixing only | | Stopwatch test; Enron slice; write the submission |
| 23-24 | Buffer | | Final check; submit |

**Dependency rule:** Opus starts on the 10 hand-written fixture emails from the story bible's D01/D02 beats in hour 0 so nobody waits on GLM.

**Cut lines (in order, if behind):** (1) Enron sanity check · (2) as-of questions · (3) PII toggle · (4) graph animation (keep static edges) · (5) human-written slice (reduce to 15 emails) · (6) Stage 3 clustering → fall back to per-thread reconcile + a global "merge by topic_label" pass. **Never cut:** quote verifier, no_decision handling, holdout scorecard, demo mode.

---

## 15. Repo layout
```
precedent/
  backend/ app.py llm.py cache.py models.py
           ingest/{parse.py,thread.py,identity.py}
           pipeline/{triage.py,extract.py,verify.py,cluster.py,reconcile.py,index.py,ask.py}
           prompts/*.md  render.py(pii)
  frontend/ (Vite+React+TS+Tailwind)
  eval/ run.py match.py judge.py report.py
  eval_private/ ground_truth.json manifest.csv eval.db   # gitignored from backend import paths
  corpus/ emails/*.eml
  demo/ cached_run.sqlite screenshots/ video/
  Makefile  README.md  SUBMISSION.md
```

## 16. Definition of done
- `make demo` loads the cached run and shows all five screens without network access.
- `make pipeline` reprocesses the 560 emails end-to-end in < 25 min.
- `make eval` prints the scorecard and writes `eval_results.json`.
- All 30 questions answer without unhandled errors; 5 return `no_decision`.
- Quote validity is 100% in the final run (proven by a test).
- Screenshots + video show input → visible result without cuts.

## 17. Assumptions (change these if wrong)
1. Runtime models are Claude via API, with the keys and budget available (§5 roles).
2. Fictional company, EUR, Rotterdam, English emails with light multilingual flavor.
3. Product name "Precedent" is a placeholder.
4. Frontend is built by Qoder from §9; Opus owns the API contract in §8.
5. Corpus = 560 emails, 40 planted decisions, 10 near-decisions, 3 conflicts (STORY_BIBLE §3-§6).
