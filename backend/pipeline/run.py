"""Pipeline orchestrator. Stages run in order; each writes to SQLite and a `runs` row with token totals.

`emit` receives progress dicts ({"event": ..., ...}); the API will forward them over SSE.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Callable

from ..llm import LLM, LLMError
from .context import _names, load_thread, thread_ids
from .extract import extract_thread
from .triage import triage_thread
from .verify import QuoteStats

Emit = Callable[[dict], None]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log_run(conn: sqlite3.Connection, run_id: str, stage: str, started: str, n_in: int, n_out: int, notes: dict) -> None:
    tin, tout, cost = conn.execute("SELECT COALESCE(SUM(tokens_in),0), COALESCE(SUM(tokens_out),0), "
                                   "COALESCE(SUM(cost_usd),0) FROM llm_calls WHERE run_id=? AND stage=?",
                                   (run_id, stage)).fetchone()
    conn.execute("INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?,?)",
                 (run_id, stage, started, _now(), n_in, n_out, tin, tout, cost, json.dumps(notes)))
    conn.commit()


async def stage_triage(llm: LLM, conn: sqlite3.Connection, tids: list[str], emit: Emit) -> dict:
    started, t0 = _now(), time.perf_counter()
    names = _names(conn)
    done, errors = 0, []

    async def one(tid: str) -> bool:
        nonlocal done
        t = load_thread(conn, tid, names)
        try:
            keep, _ = await triage_thread(llm, conn, t)
        except (LLMError, ValueError) as ex:  # recall-safe: a failed triage keeps the thread
            errors.append(f"{tid}: {ex}"[:200])
            conn.execute("INSERT OR REPLACE INTO thread_triage VALUES(?,1)", (tid,))
            conn.commit()
            keep = True
        done += 1
        emit({"event": "progress", "stage": "triage", "done": done, "total": len(tids)})
        return keep

    keeps = await asyncio.gather(*(one(t) for t in tids))
    n_keep = sum(keeps)
    notes = {"threads": len(tids), "candidates": n_keep, "filtered_pct": round(100 * (1 - n_keep / max(1, len(tids))), 1),
             "errors": errors[:10], "n_errors": len(errors), "seconds": round(time.perf_counter() - t0, 1)}
    _log_run(conn, llm.run_id, "triage", started, len(tids), n_keep, notes)
    emit({"event": "stage_done", "stage": "triage", **notes})
    return notes


async def stage_extract(llm: LLM, conn: sqlite3.Connection, tids: list[str], emit: Emit) -> dict:
    started, t0 = _now(), time.perf_counter()
    names = _names(conn)
    cand = [r[0] for r in conn.execute("SELECT thread_id FROM thread_triage WHERE has_candidate=1")]
    cand = [t for t in tids if t in set(cand)]
    stats = QuoteStats()
    stances: Counter = Counter()
    done, discarded, errors, n_records = 0, 0, [], 0

    async def one(tid: str) -> None:
        nonlocal done, discarded, n_records
        t = load_thread(conn, tid, names)
        local = QuoteStats()
        try:
            stored, dropped = await extract_thread(llm, conn, t, local)
        except (LLMError, ValueError) as ex:
            errors.append(f"{tid}: {ex}"[:200])
            stored, dropped = [], 0
        stats.add(local)
        discarded += dropped
        n_records += len(stored)
        for r in stored:
            stances[r["stance"]] += 1
            if r["stance"] == "final":
                emit({"event": "decision_found", "record_id": r["record_id"], "text": r["decision_text"],
                      "date": r["decision_date"], "topic": r["topic_label"]})
        done += 1
        emit({"event": "progress", "stage": "extract", "done": done, "total": len(cand)})

    await asyncio.gather(*(one(t) for t in cand))
    notes = {"candidate_threads": len(cand), "records": n_records, "by_stance": dict(stances),
             "records_discarded_no_evidence": discarded, **stats.as_dict(),
             "dropped_examples": stats.dropped_examples[:5], "errors": errors[:10], "n_errors": len(errors),
             "seconds": round(time.perf_counter() - t0, 1)}
    _log_run(conn, llm.run_id, "extract", started, len(cand), n_records, notes)
    emit({"event": "stage_done", "stage": "extract", **notes})
    return notes


STAGES = {"triage": stage_triage, "extract": stage_extract}


async def run_pipeline(conn: sqlite3.Connection, stages: list[str], run_id: str | None = None,
                       threads: list[str] | None = None, emit: Emit = lambda e: None) -> dict:
    run_id = run_id or "run-" + uuid.uuid4().hex[:8]
    llm = LLM(conn, run_id=run_id)
    tids = threads or thread_ids(conn)
    out = {"run_id": run_id}
    for s in stages:
        emit({"event": "stage_start", "stage": s})
        out[s] = await STAGES[s](llm, conn, tids, emit)
    return out
