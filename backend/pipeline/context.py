"""Load threads from SQLite and render them for prompts.

Messages are shown to the model under short aliases (m1, m2, ...) and mapped back to real Message-IDs in code:
cheaper, and the model cannot mangle a long ID.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass
class Msg:
    alias: str
    message_id: str
    sender: str
    sender_addr: str
    to: list[str]
    local_dt: datetime
    subject: str
    new_text: str
    fwd_text: str
    fwd_meta: dict | None
    quoted_text: str
    parent_in_thread: bool

    @property
    def date(self) -> str:
        return self.local_dt.strftime("%Y-%m-%d")


@dataclass
class Thread:
    thread_id: str
    subject: str
    msgs: list[Msg]
    participants: list[str]

    def by_alias(self) -> dict[str, Msg]:
        return {m.alias: m for m in self.msgs}

    def by_id(self) -> dict[str, Msg]:
        return {m.message_id: m for m in self.msgs}


def _local(sent_at: str, tz: str | None) -> datetime:
    dt = datetime.fromisoformat(sent_at)
    if tz and len(tz) == 5:
        sign = 1 if tz[0] == "+" else -1
        dt = dt.astimezone(timezone(sign * timedelta(hours=int(tz[1:3]), minutes=int(tz[3:5]))))
    return dt


def _names(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute("SELECT i.value, p.canonical_name FROM identities i JOIN people p ON p.id=i.person_id "
                        "WHERE i.kind='email'").fetchall()
    return {r[0]: r[1] for r in rows}


def load_thread(conn: sqlite3.Connection, thread_id: str, names: dict[str, str] | None = None) -> Thread:
    names = names if names is not None else _names(conn)
    rows = conn.execute("SELECT * FROM emails WHERE thread_id=? ORDER BY sent_at, message_id", (thread_id,)).fetchall()
    ids = {r["message_id"] for r in rows}
    msgs = []
    for i, r in enumerate(rows, start=1):
        to = json.loads(r["to_addrs"] or "[]") + json.loads(r["cc_addrs"] or "[]")
        msgs.append(Msg(
            alias=f"m{i}", message_id=r["message_id"],
            sender=names.get(r["from_addr"], r["from_name"] or r["from_addr"]), sender_addr=r["from_addr"],
            to=[names.get(a, a) for a in to], local_dt=_local(r["sent_at"], r["sent_tz"]), subject=r["subject"] or "",
            new_text=r["new_text"] or "", fwd_text=r["fwd_text"] or "",
            fwd_meta=json.loads(r["fwd_meta"]) if r["fwd_meta"] else None, quoted_text=r["quoted_text"] or "",
            parent_in_thread=bool(r["in_reply_to"]) and r["in_reply_to"] in ids,
        ))
    t = conn.execute("SELECT * FROM threads WHERE thread_id=?", (thread_id,)).fetchone()
    return Thread(thread_id, msgs[0].subject if msgs else "", msgs, json.loads(t["participants"]) if t else [])


def thread_ids(conn: sqlite3.Connection) -> list[str]:
    return [r[0] for r in conn.execute("SELECT thread_id FROM threads ORDER BY first_at, thread_id")]


def render_thread(t: Thread, fwd_limit: int | None = None, with_quoted_context: bool = True) -> str:
    """One block per message. Only NEW and FORWARDED text is citable; quoted text appears only when the replied-to
    message is not itself in the thread, and is labelled as context."""
    out = [f"THREAD {t.thread_id}  subject: {t.subject!r}  ({len(t.msgs)} message{'s' * (len(t.msgs) != 1)})"]
    for m in t.msgs:
        head = (f"\n=== [{m.alias}] {m.local_dt.strftime('%a %Y-%m-%d %H:%M')}  From: {m.sender}"
                f"  To: {', '.join(m.to) or '-'}\nSubject: {m.subject}")
        out.append(head)
        out.append("NEW TEXT:\n" + (m.new_text.strip() or "(empty)"))
        if m.fwd_text:
            meta = m.fwd_meta or {}
            who = meta.get("from_name") or meta.get("from_addr") or "unknown"
            when = (meta.get("date") or meta.get("date_raw") or "unknown date")[:10]
            fwd = m.fwd_text if fwd_limit is None else m.fwd_text[:fwd_limit]
            out.append(f"FORWARDED TEXT (originally written by {who}, {when}):\n{fwd}")
        if with_quoted_context and m.quoted_text and not m.parent_in_thread:
            out.append("QUOTED HISTORY (context only, NOT citable, may be outdated):\n" + m.quoted_text[:800])
    return "\n".join(out)


def people_directory(conn: sqlite3.Connection, addrs: list[str] | None = None) -> str:
    """Internal people plus the given participants, with roles inferred from signatures."""
    rows = conn.execute(
        "SELECT p.*, group_concat(i.value, ', ') emails FROM people p JOIN identities i ON i.person_id=p.id "
        "AND i.kind='email' GROUP BY p.id ORDER BY p.is_internal DESC, p.canonical_name").fetchall()
    wanted = set(addrs or [])
    lines = []
    for r in rows:
        emails = r["emails"].split(", ")
        if not (r["is_internal"] or wanted & set(emails)):
            continue
        role = r["role_guess"] or "role unknown"
        side = "internal" if r["is_internal"] else f"external, {r['org'] or 'unknown org'}"
        lines.append(f"- {r['canonical_name']}: {role} ({side})")
    return "\n".join(lines)


def related_subjects(conn: sqlite3.Connection, t: Thread, limit: int = 10) -> list[str]:
    """Other threads sharing ≥ 2 participants within ±14 days (subject lines only, as cross-thread hints)."""
    if not t.msgs:
        return []
    mine = set(t.participants)
    lo = (t.msgs[0].local_dt - timedelta(days=14)).astimezone(timezone.utc).isoformat()
    hi = (t.msgs[-1].local_dt + timedelta(days=14)).astimezone(timezone.utc).isoformat()
    out = []
    for r in conn.execute("SELECT thread_id, subject_norm, first_at, participants FROM threads "
                          "WHERE thread_id != ? AND last_at >= ? AND first_at <= ? ORDER BY first_at",
                          (t.thread_id, lo, hi)):
        if len(mine & set(json.loads(r["participants"]))) >= 2:
            out.append(f"{r['first_at'][:10]}: {r['subject_norm']}")
    return out[:limit]
