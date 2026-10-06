"""Stage 2: extraction (CORE, one call per candidate thread) + 2b quote verification."""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import date
from pathlib import Path

from ..llm import LLM
from ..models import DecisionRecord, ExtractionResult
from .context import Thread, people_directory, related_subjects, render_thread
from .verify import QuoteStats, verify_quote

BASE_PROMPT = (Path(__file__).resolve().parent.parent / "prompts" / "extract.md").read_text(encoding="utf-8")
FORMAT_NOTES = """
CLARIFICATIONS
- Open-ended deferrals are not decisions: "not now", "park it", "hold off for now", "let's revisit later", "put it on
  ice" with no committed date or chosen alternative. Do not output a record for them (or output stance=proposed if a
  concrete proposal was put forward and left open). By contrast, changing the timing of an already agreed plan to a
  specific date or milestone ("we keep the current vendor and move the switch to Q3") IS a decision.
- One person's opinion, preference or recommendation that nobody with authority confirms is stance=proposed.
- Trivial logistics are out of scope even when settled: office furniture, equipment colours, kitchen or snack
  supplies, desk or room bookings, meeting slots, social events. Do not output them.
- A plan the sender takes back ("scratch that", "ignore my last email", "actually, hold off") is stance=retracted.
- An offer, price or commitment that has already been communicated to an outside party (a customer, vendor or
  candidate) is stance=final from the company's side, even if the sender may lack authority for it; record the doubt
  in authority_note instead of downgrading the stance. Whether it was later replaced is decided in a later step.
- When someone with authority announces something as settled ("we're starting X next week", a recap stating X was
  agreed), that is a decision record with stance=final even if others object afterwards; objections that do not
  reverse it are evidence with role=objection, not a reason to drop the record.
- When people disagree about what was agreed (one says X was decided, another says the agreement or their
  understanding was Y), output one record per version, each with stance=final, decided_by = the person asserting it,
  and that person's own evidence; mention the disagreement in rationale. Do not merge the versions or pick one; a
  later step decides whether it is a real conflict.

FORMAT NOTES
- evidence.message_id is the message alias exactly as shown in the thread (m1, m2, ...).
- Quotes come only from a message's NEW TEXT or FORWARDED TEXT, never from QUOTED HISTORY.
- decided_by uses names as they appear in the people directory.
- decision_date is the calendar date shown on the decisive message, formatted YYYY-MM-DD.
"""
SYSTEM = BASE_PROMPT.rstrip() + "\n" + FORMAT_NOTES
DECISIVE_ROLES = ("approval", "confirmation", "reversal")


def build_prompt(conn: sqlite3.Connection, t: Thread) -> str:
    parts = ["PEOPLE DIRECTORY (roles inferred from email signatures; may be incomplete):",
             people_directory(conn, t.participants)]
    hints = related_subjects(conn, t)
    if hints:
        parts += ["", "OTHER THREADS WITH OVERLAPPING PARTICIPANTS (within 14 days; subjects only, for context):",
                  *[f"- {h}" for h in hints]]
    parts += ["", render_thread(t)]
    return "\n".join(parts)


def _valid_date(s: str) -> bool:
    try:
        date.fromisoformat(s)
        return True
    except ValueError:
        return False


def store_records(conn: sqlite3.Connection, t: Thread, result: ExtractionResult, stats: QuoteStats) -> list[dict]:
    """Verify every quote, drop records with no verified evidence, persist the rest. Returns stored records."""
    aliases = t.by_alias()
    texts = {m.message_id: (m.new_text, m.fwd_text) for m in t.msgs}
    by_id = t.by_id()

    old = [r[0] for r in conn.execute("SELECT record_id FROM records WHERE thread_id=?", (t.thread_id,))]
    conn.executemany("DELETE FROM evidence WHERE owner_kind='record' AND owner_id=?", [(r,) for r in old])
    conn.execute("DELETE FROM records WHERE thread_id=?", (t.thread_id,))

    stored = []
    for i, rec in enumerate(result.records, start=1):
        checked = []
        for ev in rec.evidence:
            alias = re.sub(r"[\[\]\s]", "", ev.message_id)
            mid = aliases[alias].message_id if alias in aliases else ev.message_id
            checked.append(verify_quote(mid, ev.quote, ev.role, texts, stats))
        good = [q for q in checked if q.verified]
        if not good:
            continue
        ddate = rec.decision_date
        if not _valid_date(ddate):
            decisive = [q for q in good if q.role in DECISIVE_ROLES] or good
            ddate = max(by_id[q.message_id].date for q in decisive)
        rid = f"R-{t.thread_id[2:]}-{i:02d}"
        conn.execute(
            "INSERT INTO records(record_id, thread_id, topic_label, decision_text, stance, decision_type, decided_by,"
            " decision_date, rationale, alternatives, conditions, overrides_hint, authority_note, confidence)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (rid, t.thread_id, rec.topic_label, rec.decision_text, rec.stance, rec.decision_type,
             json.dumps(rec.decided_by, ensure_ascii=False), ddate, rec.rationale,
             json.dumps(rec.alternatives, ensure_ascii=False), rec.conditions, rec.overrides_hint, rec.authority_note,
             rec.confidence))
        for q in checked:
            conn.execute("INSERT INTO evidence(owner_kind, owner_id, message_id, quote, role, verified)"
                         " VALUES('record',?,?,?,?,?)", (rid, q.message_id, q.quote, q.role, int(q.verified)))
        stored.append({"record_id": rid, "thread_id": t.thread_id, "topic_label": rec.topic_label,
                       "decision_text": rec.decision_text, "stance": rec.stance, "decision_date": ddate,
                       "n_evidence": len(good)})
    conn.commit()
    return stored


def _strong_signal(conn: sqlite3.Connection, thread_id: str) -> bool:
    return conn.execute("SELECT 1 FROM triage WHERE thread_id=? AND signal IN ('decision','approval','reversal') "
                        "LIMIT 1", (thread_id,)).fetchone() is not None


async def extract_thread(llm: LLM, conn: sqlite3.Connection, t: Thread, stats: QuoteStats) -> tuple[list[dict], int]:
    """Returns (stored records, number of records discarded for lack of verified evidence)."""
    prompt = build_prompt(conn, t)
    res = await llm.structured("CORE", SYSTEM, prompt, ExtractionResult, stage="extract")
    if not res.records and _strong_signal(conn, t.thread_id):
        # capped reasoning sometimes reads a disputed or informal decision as "nothing settled"; think longer
        res = await llm.structured("CORE_DEEP", SYSTEM, prompt, ExtractionResult, stage="extract_deep")
    stored = store_records(conn, t, res, stats)
    return stored, len(res.records) - len(stored)


__all__ = ["extract_thread", "store_records", "build_prompt", "SYSTEM", "DecisionRecord"]
