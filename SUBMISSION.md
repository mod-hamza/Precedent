# Precedent

**"Why did we decide that?" Answered in seconds, with receipts.**

We help small teams that run on email solve lost and re-argued decisions through a decision ledger and an AI that
extracts, links and cites every decision, cutting the time to answer "why did we choose this?" from minutes of inbox
searching to seconds, with **87%** decision recall and **100%** verbatim evidence on the held-out part of a 560-email
benchmark with hidden ground truth.

> Sections marked **[TEAM]** need your input. All numbers come from `eval/results/scorecard.md`.

---

## 01 Project Summary

Upload a mailbox (`.eml`, `.mbox` or a zip). Precedent builds a **decision ledger**: every business decision with its
rationale, alternatives, who decided, when, its status (active / superseded / amended / contested) and quoted evidence
from specific emails. Ask questions in plain language and get cited answers, including an honest "no decision found".

What makes it more than chat-with-your-inbox:

1. Decisions have a **lifecycle**: proposals, decisions, amendments and reversals are linked into a graph.
2. **Implicit decisions** ("ok saturday then", a thumbs-up to a proposal) are detected.
3. **Cross-thread stitching**: one decision spread over threads, recaps and forwards becomes one record.
4. **Contested decisions** show both versions side by side; Precedent never picks a winner.
5. **Authority check**: flags decisions closed by someone without apparent authority, neutrally.
6. **Programmatic quote verification**: every quote shown is checked in code as a verbatim substring of the cited
   email, or it is dropped. No invented evidence reaches the screen.
7. A **benchmark and scorecard** ship with it, so every claim here is measured.

## 02 Problem & Users

Small teams make decisions in email threads, reply-alls and forwarded recaps. Weeks later nobody can find why a vendor
was chosen or which number was approved, so decisions get re-argued or quietly contradicted.

| Persona | Pain | What Precedent answers |
|---|---|---|
| Founder / CEO | "Didn't we already settle this?" | "Did we ever decide on X?" -> a cited yes, or "No decision; closest: ..." |
| New hire | Joined mid-flight, no history | "Why is the database still on NimbusHost?" -> the full reasoning chain |
| Finance lead | Needs the *current* approved number | "What's the renewal discount?" -> the approved value, and which offer was unauthorised |

## 03 Solution & Flow

```
.eml/.mbox -> 0 Parse, thread, identities -> 1 Triage -> 2 Extract + quote verifier -> 3 Cluster by topic
           -> 4 Reconcile (decisions, edges, conflicts, current state) -> 5 Index -> 6 Ask (cited answers)
```

- **Stage 0** (code): MIME parsing, splitting each email into the sender's new words / quoted history / forwarded
  text (forwarded evidence is attributed to the original author and date), signature stripping, threading
  (References / In-Reply-To with a subject fallback), identity resolution (one person, several addresses).
- **Stage 1 Triage** (fast model): labels every message, keeps any thread that might hold a decision. Recall-biased:
  a model slip can only add threads.
- **Stage 2 Extract**: decision records with stance, decider, date, rationale, alternatives and 1-5 quotes.
- **Quote verifier** (code): normalised matching, but what is stored is always the original span of the email.
- **Stage 3 Cluster**: groups records by evolving topic so a decision and its later changes meet.
- **Stage 4 Reconcile**: merges duplicates, builds supersedes / amends / refines edges, marks conflicts, writes
  each topic's current state.
- **Stage 5-6 Ask**: hybrid search (BM25 + embeddings), decision chains expanded, answer generated, every citation
  re-verified in code (one retry), confidence computed deterministically.

UI: Ingest (live pipeline + funnel), Timeline (topic swimlanes with lifecycle arrows), Decision drawer, Ask,
Conflicts, Scorecard. **[TEAM: screenshots]**

## 04 AI, Data & Tools

**Models** (Alibaba Cloud Model Studio, OpenAI-compatible endpoint; swappable per role via configuration):

| Role | Model | Used for |
|---|---|---|
| FAST | qwen3.8-flash (reasoning off) | triage, identity adjudication, question classification |
| CORE | qwen3.8-max (reasoning capped at 3k tokens; 12k second pass on hard threads) | extraction |
| REASON | deepseek-v4-pro | clustering, reconciliation |
| ANSWER | qwen3.8-max (reasoning off, for latency) | cited answers |
| JUDGE | deepseek-v4-pro | evaluation only (a different model family from the extractor) |
| Embeddings | all-MiniLM-L6-v2, local (sentence-transformers) | retrieval |

Every model output is constrained to a JSON schema and validated (Pydantic) with one repair retry; every call is
cached on a hash of model + prompt + schema, so re-runs are free and the demo is reproducible offline.

**Data.** A synthetic mailbox for a fictional 22-person Rotterdam company: 560 emails, 40 planted decisions
(explicit, implicit, cross-thread, amended, superseded), 10 near-decisions (deferrals, unapproved proposals,
retractions), 3 conflicts, plus filler with traps (quoted old decisions, forwards, hypotheticals, trivial logistics,
innocent number differences). Generated with GLM 5.3 from a story bible, assembled into real `.eml` files with
threading breaks, reply quoting styles and signatures. Split: dev 349 emails / holdout 211 emails.

**Integrity.** The pipeline never reads the ground truth (a test enforces it). During the build we found and fixed a
label leak: the original Message-IDs and filenames contained the planted thread keys (D13 / F176), which would have
let a model tell decisions from filler by ID; they were replaced with opaque IDs before any tuning. Prompts were tuned
on dev only; the holdout was run once, after freezing (git tags `holdout-freeze` and `holdout-results`).

**Development tools.** **[TEAM: list the tools and assistants used to build this, honestly.]**

## 05 Demo Evidence

**[TEAM: 8 screenshots from `demo/screenshots/` and the video link.]** Demo mode (`make demo`) replays the cached run
with no network access.

## 06 Business Value

Scorecard. Dev was used for tuning; the holdout was run **once** on the frozen commit (`holdout-freeze`, 0de46ce).
Full tables in `eval/results/scorecard.md`.

| Metric | Target | Dev (25 decisions) | Holdout (15 decisions) |
|---|---|---|---|
| Decision recall | >= 85% | 98% | **87%** |
| Decision precision (strict, vs the planted set) | >= 85% | 74% | **46%** |
| ... of the unmatched predictions, judged genuine decisions | context | 8 of 8 | 12 of 15 |
| Near-decision false positives | <= 2 of 10 | 0 of 5 | **0 of 5** (0 of 10 overall) |
| Supersession-link accuracy | >= 80% | 90% | **33%** (1 of 3) |
| Conflicts detected | >= 2 of 3 | 2 of 2 | **0 of 1** (2 of 3 overall) |
| Quote validity | 100% | 100% | **100%** (enforced in code, proven by a test) |
| Evidence support | >= 90% | 100% | **100%** |
| Q&A accuracy (rubric, LLM-judged) | >= 85% of 30 | 68% of 19 | **68% of 11** |
| "No decision" correctness | 5/5 | 4/4 | **1/1** (5/5 overall) |
| Answer latency p50 | < 8 s | 15.8 s | **17.3 s** |
| Triage recall | >= 98% | 100% | **100%** |
| Pipeline wall-clock, 560 emails | < 25 min | 9.8 min (Stages 1-5, cached re-runs are free) | |

**Reading the numbers honestly.**
- *Precision* is strict against the 40 planted decisions, so real decisions the planted set does not list count as
  errors; the judge rated 12 of the 15 unmatched holdout predictions as genuine decisions (e.g. small approvals).
- *Holdout misses.* The Redline 15% discount (an offer a salesperson sent without sign-off) was extracted as a
  "proposal" instead of an unauthorised commitment, which also cost its supersession link. The office-lease renewal
  *is* in the ledger ("Renew the Keizersgracht office lease for 12 months at EUR 6,200") but the judge did not match it
  to the reference wording ("Rotterdam office lease"); we report the judged number unchanged. The Q2 marketing budget
  dispute (EUR 40k vs 30k) was recorded as separate decisions instead of a conflict.
- *Latency.* Answers use a 2k-token reasoning budget: dev Q&A was 63% without it at ~7 s. We chose accuracy over the
  8 s target; demo mode serves cached answers instantly.
- *Post-holdout change.* After the holdout run we fixed the first miss (offers already sent to a customer are now
  recorded as decisions with an authority note). The holdout column above is from the frozen commit and was not
  re-run; the demo runs the fixed version. Two further post-holdout changes: internal people whose signatures show no role get one inferred from behaviour (e.g. the CEO signs "M"), and sentences without a verified citation are removed from answers. Dev after these changes: recall 96%, precision 67%, supersession 80%, conflicts 2 of 2, near-decision false positives 0 of 5, Q&A 68% of 19, no-decision 4/4. Live Q&A scores vary by about +/-7 points between identical runs (the answer model and the LLM judge both vary), so treat single Q&A numbers as approximate.

**Stopwatch test [TEAM]:** manual search in a raw mailbox viewer vs Precedent's answer time on 5 questions.

## 07 Risks & Next Steps

**Limits.** Synthetic corpus (LLM-written); email only; attachments only by filename; decisions made by phone or in
person are invisible (a banner says so); authority is inferred from signatures and behaviour, not an org chart;
English-dominant; tested at 560 emails (target <= 5k). Strict precision counts genuine decisions that are not among
the 40 planted ones as errors; the scorecard reports how many of those the judge considers genuine.

**Controls built in.** Citations or silence (unverifiable quotes are dropped); calibrated "no decision" answers;
contested never silently resolved; neutral authority flags; PII redaction toggle (emails, phones, IBANs masked at
render time); "Dispute this decision" feedback; honest holdout evaluation.

**Roadmap.** Live Gmail / Outlook OAuth; WhatsApp and Slack exports (the connector interface exists); role-based
visibility; local-model mode for sensitive mailboxes.

## 08 Team & Ownership

**[TEAM]**
