"""Stage 1: triage (FAST, one call per thread, recall-biased)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from ..llm import LLM
from ..models import TriageResult
from .context import Thread, render_thread

PROMPT = (Path(__file__).resolve().parent.parent / "prompts" / "triage.md").read_text(encoding="utf-8")
KEEP_SIGNALS = {"proposal", "approval", "decision", "reversal", "commitment"}


def has_candidate(result: TriageResult) -> bool:
    """Model flag OR the PRD rule, so a model slip can only add threads, never drop them."""
    sigs = [m.signal for m in result.messages]
    if result.has_candidate or KEEP_SIGNALS & set(sigs):
        return True
    return any(s == "question" and any(x in ("approval", "decision") for x in sigs[i + 1:]) for i, s in enumerate(sigs))


async def triage_thread(llm: LLM, conn: sqlite3.Connection, t: Thread) -> tuple[bool, TriageResult]:
    user = render_thread(t, fwd_limit=600, with_quoted_context=False)
    res = await llm.structured("FAST", PROMPT, user, TriageResult, stage="triage")
    aliases = t.by_alias()
    keep = has_candidate(res)
    conn.execute("DELETE FROM triage WHERE thread_id=?", (t.thread_id,))
    for m in res.messages:
        msg = aliases.get(m.message_id.strip("[] "))
        if msg is not None:
            conn.execute("INSERT OR REPLACE INTO triage VALUES(?,?,?,?)", (t.thread_id, msg.message_id, m.signal, m.note))
    conn.execute("INSERT OR REPLACE INTO thread_triage VALUES(?,?)", (t.thread_id, int(keep)))
    conn.commit()
    return keep, res
