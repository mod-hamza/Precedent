"""Stage 0 driver: parse -> dedupe -> thread -> identities -> SQLite."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .identity import resolve_identities
from .parse import ParsedEmail, iter_path
from .thread import build_threads

_INGEST_TABLES = ("emails", "people", "identities", "threads")


def load_emails(paths: list[Path]) -> tuple[list[ParsedEmail], int]:
    seen: dict[str, ParsedEmail] = {}
    dupes = 0
    for p in paths:
        for e in iter_path(p):
            if e.message_id in seen:
                dupes += 1
                continue
            seen[e.message_id] = e
    emails = sorted(seen.values(), key=lambda e: (e.sent_at, e.message_id))
    return emails, dupes


async def run_stage0(conn: sqlite3.Connection, paths: list[Path], llm=None, run_id: str | None = None) -> dict:
    started = datetime.now(timezone.utc).isoformat()
    emails, dupes = load_emails(paths)
    thread_of, thread_rows = build_threads(emails)
    people, addr_to_pid = await resolve_identities(emails, llm)

    for t in _INGEST_TABLES:
        conn.execute(f"DELETE FROM {t}")
    for e in emails:
        row = e.row()
        row["thread_id"] = thread_of[e.message_id]
        row["from_person_id"] = addr_to_pid.get(e.from_addr)
        cols = ", ".join(row)
        conn.execute(f"INSERT INTO emails({cols}) VALUES({', '.join('?' * len(row))})", list(row.values()))
    for t in thread_rows:
        conn.execute("INSERT INTO threads VALUES(?,?,?,?,?,?)",
                     (t["thread_id"], t["subject_norm"], t["first_at"], t["last_at"], t["n_msgs"],
                      json.dumps(t["participants"])))
    for p in people:
        conn.execute("INSERT INTO people(id, canonical_name, role_guess, org, is_internal) VALUES(?,?,?,?,?)",
                     (p["id"], p["canonical_name"], p["role_guess"], p["org"], p["is_internal"]))
        for kind, value in p["identities"]:
            conn.execute("INSERT OR IGNORE INTO identities(person_id, kind, value) VALUES(?,?,?)", (p["id"], kind, value))
    stats = {
        "emails": len(emails), "duplicates_skipped": dupes, "threads": len(thread_rows),
        "multi_message_threads": sum(1 for t in thread_rows if t["n_msgs"] > 1),
        "people": len(people), "internal_people": sum(p["is_internal"] for p in people),
        "with_quoted": sum(1 for e in emails if e.quoted_text), "with_forward": sum(1 for e in emails if e.fwd_text),
    }
    conn.execute("INSERT INTO runs(run_id, stage, started_at, finished_at, n_in, n_out, tokens_in, tokens_out, cost_usd, notes)"
                 " VALUES(?,?,?,?,?,?,0,0,0,?)",
                 (run_id, "parse", started, datetime.now(timezone.utc).isoformat(), len(emails) + dupes, len(emails),
                  json.dumps(stats)))
    conn.commit()
    return stats
