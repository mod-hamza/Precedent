"""Stage 4: reconcile each cluster into decisions, lifecycle edges, conflicts and a current state (REASON).

Clusters with >= 2 records or any non-final record go to the model; a lone final record becomes a decision directly.
After each call: every quote is re-verified (unverifiable quotes are dropped; a decision left with no verified evidence
inherits its records' verified evidence, else it is dropped), statuses are made consistent with edges, and stable ids
DEC-0001... are assigned by date across the whole ledger.
"""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from ..llm import LLM
from ..models import ReconcileResult
from .context import _local, people_directory
from .verify import QuoteStats, verify_quote

PROMPT = (Path(__file__).resolve().parent.parent / "prompts" / "reconcile.md").read_text(encoding="utf-8")
NON_FINAL = {"proposed", "conditional", "tentative", "retracted"}
MAX_EMAILS = 40  # above this, only cited emails go in the prompt


@dataclass
class DraftDecision:
    cluster_id: str
    canonical_text: str
    decided_by: list[str]
    decided_at: str
    rationale: str | None
    alternatives: list[str]
    decision_type: str
    status: str
    authority_flag: bool
    authority_note: str | None
    confidence: float
    record_ids: list[str]
    evidence: list[tuple[str, str, str]]  # (message_id, quote, role), all verified
    temp: str = ""
    final_id: str = ""


@dataclass
class ClusterOutcome:
    cluster_id: str
    decisions: list[DraftDecision] = field(default_factory=list)
    edges: list[tuple[str, str, str, str, str | None, str | None]] = field(default_factory=list)  # temp ids
    conflicts: list[dict] = field(default_factory=list)
    current_state: str | None = None
    topic: str | None = None
    non_decisions: int = 0


def _records(conn: sqlite3.Connection, cluster_id: str) -> list[sqlite3.Row]:
    return conn.execute("SELECT r.*, t.subject_norm FROM records r JOIN threads t USING(thread_id) "
                        "WHERE cluster_id=? ORDER BY decision_date, record_id", (cluster_id,)).fetchall()


def _record_evidence(conn: sqlite3.Connection, rid: str) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM evidence WHERE owner_kind='record' AND owner_id=? AND verified=1 ORDER BY id",
                        (rid,)).fetchall()


def _emails(conn: sqlite3.Connection, ids: list[str]) -> dict[str, sqlite3.Row]:
    out = {}
    for mid in ids:
        r = conn.execute("SELECT * FROM emails WHERE message_id=?", (mid,)).fetchone()
        if r is not None:
            out[mid] = r
    return out


def build_prompt(conn: sqlite3.Connection, recs: list[sqlite3.Row]) -> tuple[str, dict[str, str], dict[str, str]]:
    """Returns (prompt, record alias -> record_id, email alias -> message_id)."""
    ev = {r["record_id"]: _record_evidence(conn, r["record_id"]) for r in recs}
    mids: list[str] = []
    for rows in ev.values():
        for e in rows:
            if e["message_id"] not in mids:
                mids.append(e["message_id"])
    # Whole threads, not just cited emails: the other side of a dispute is often in a message no record cited.
    thread_mids = [m for (m,) in conn.execute(
        f"SELECT message_id FROM emails WHERE thread_id IN ({','.join('?' * len(recs))}) ORDER BY sent_at",
        [r["thread_id"] for r in recs])]
    if len(set(mids) | set(thread_mids)) <= MAX_EMAILS:
        mids += [m for m in thread_mids if m not in mids]
    emails = _emails(conn, mids)
    mids = sorted(emails, key=lambda m: emails[m]["sent_at"])
    e_alias = {m: f"e{i + 1}" for i, m in enumerate(mids)}
    r_alias = {r["record_id"]: f"r{i + 1}" for i, r in enumerate(recs)}
    names = {row[0]: row[1] for row in conn.execute(
        "SELECT i.value, p.canonical_name FROM identities i JOIN people p ON p.id=i.person_id WHERE i.kind='email'")}

    out = ["PEOPLE DIRECTORY (roles inferred from email signatures; may be incomplete):",
           people_directory(conn, [emails[m]["from_addr"] for m in mids]), "", "RECORDS"]
    for r in recs:
        out.append(f"\n[{r_alias[r['record_id']]}] {r['decision_date']}  stance={r['stance']}  type={r['decision_type']}"
                   f"  thread={r['subject_norm']!r}")
        out.append(f"  topic: {r['topic_label']}\n  decision: {r['decision_text']}")
        out.append(f"  decided_by: {', '.join(json.loads(r['decided_by'] or '[]')) or '-'}")
        for k in ("rationale", "conditions", "overrides_hint", "authority_note"):
            if r[k]:
                out.append(f"  {k}: {r[k]}")
        alts = json.loads(r["alternatives"] or "[]")
        if alts:
            out.append(f"  alternatives: {'; '.join(alts)}")
        for e in ev[r["record_id"]]:
            out.append(f"  evidence [{e_alias.get(e['message_id'], '?')}] ({e['role']}): \"{e['quote']}\"")
    out.append("\nEMAILS (only NEW TEXT and FORWARDED TEXT may be quoted)")
    for m in mids:
        e = emails[m]
        dt = _local(e["sent_at"], e["sent_tz"]).strftime("%a %Y-%m-%d %H:%M")
        out.append(f"\n=== [{e_alias[m]}] {dt}  From: {names.get(e['from_addr'], e['from_name'])}  "
                   f"Subject: {e['subject']}\nNEW TEXT:\n{e['new_text'] or '(empty)'}")
        if e["fwd_text"]:
            meta = json.loads(e["fwd_meta"] or "{}")
            out.append(f"FORWARDED TEXT (originally written by {meta.get('from_name') or meta.get('from_addr')}, "
                       f"{(meta.get('date') or meta.get('date_raw') or '?')[:10]}):\n{e['fwd_text']}")
    return "\n".join(out), {v: k for k, v in r_alias.items()}, {v: k for k, v in e_alias.items()}


def _texts(conn: sqlite3.Connection, mids: list[str]) -> dict[str, tuple[str, str]]:
    return {m: (r["new_text"] or "", r["fwd_text"] or "") for m, r in _emails(conn, mids).items()}


def direct_decision(conn: sqlite3.Connection, cid: str, r: sqlite3.Row) -> ClusterOutcome:
    ev = [(e["message_id"], e["quote"], e["role"]) for e in _record_evidence(conn, r["record_id"])]
    d = DraftDecision(cid, r["decision_text"], json.loads(r["decided_by"] or "[]"), r["decision_date"], r["rationale"],
                      json.loads(r["alternatives"] or "[]"), r["decision_type"], "active", bool(r["authority_note"]),
                      r["authority_note"], r["confidence"] or 0.0, [r["record_id"]], ev, temp="d1")
    return ClusterOutcome(cid, [d], topic=r["topic_label"])


def _uncovered_final(res: ReconcileResult, recs: list[sqlite3.Row], r_map: dict[str, str]) -> list[str]:
    covered = {x.strip() for d in res.decisions for x in d.merged_record_ids}
    covered |= {x.strip() for n in res.non_decisions for x in n.record_ids}
    finals = {a for a, rid in r_map.items() if any(r["record_id"] == rid and r["stance"] == "final" for r in recs)}
    return sorted(finals - covered, key=lambda a: int(a[1:]) if a[1:].isdigit() else 0)


def _fix_statuses(out: ClusterOutcome) -> None:
    by = {d.temp: d for d in out.decisions}
    for src, dst, kind, scope, _, _ in out.edges:
        if dst in by and by[dst].status != "contested":
            if kind == "supersedes":
                by[dst].status = "superseded"
            elif kind == "amends" and by[dst].status == "active":
                by[dst].status = "amended"


async def reconcile_cluster(llm: LLM, conn: sqlite3.Connection, cid: str, stats: QuoteStats) -> ClusterOutcome:
    recs = _records(conn, cid)
    # A lone final record becomes a decision directly, unless the extractor raised an authority doubt: whether that
    # is a real flag (nobody with authority approved before it went out) needs the reasoning step.
    if len(recs) == 1 and recs[0]["stance"] not in NON_FINAL and not recs[0]["authority_note"]:
        return direct_decision(conn, cid, recs[0])

    prompt, r_map, e_map = build_prompt(conn, recs)
    res = await llm.structured("REASON", PROMPT, prompt, ReconcileResult, stage="reconcile")
    missing = _uncovered_final(res, recs, r_map)
    if missing:  # every final record must be merged into a decision or explained as a non-decision
        retry = (prompt + "\n\nYOUR PREVIOUS ANSWER LEFT THESE FINAL RECORDS UNACCOUNTED FOR: " + ", ".join(missing)
                 + ". Every record must appear in some decision's merged_record_ids or in non_decisions with a reason.")
        res2 = await llm.structured("REASON", PROMPT, retry, ReconcileResult, stage="reconcile_retry")
        missing2 = _uncovered_final(res2, recs, r_map)
        if len(missing2) < len(missing):
            res, missing = res2, missing2
    texts = _texts(conn, list(e_map.values()))
    rec_by_id = {r["record_id"]: r for r in recs}

    def check(evs) -> list[tuple[str, str, str]]:
        good = []
        for ev in evs:
            alias = re.sub(r"[\[\]\s]", "", ev.message_id)
            mid = e_map.get(alias, ev.message_id)
            q = verify_quote(mid, ev.quote, ev.role, texts, stats)
            if q.verified and (q.message_id, q.quote) not in {(g[0], g[1]) for g in good}:
                good.append((q.message_id, q.quote, q.role))
        return good

    out = ClusterOutcome(cid, topic=res.cluster_topic, current_state=res.current_state,
                         non_decisions=sum(len(n.record_ids) for n in res.non_decisions))
    for d in res.decisions:
        rids = [r_map[x.strip()] for x in d.merged_record_ids if x.strip() in r_map]
        ev = check(d.evidence)
        if not ev:  # citations or silence: fall back to the merged records' own verified evidence
            ev = [(e["message_id"], e["quote"], e["role"]) for rid in rids for e in _record_evidence(conn, rid)]
        if not ev:
            continue
        dtype = d.decision_type if d.decision_type in ("explicit", "implicit") else \
            (rec_by_id[rids[0]]["decision_type"] if rids else "explicit")
        out.decisions.append(DraftDecision(cid, d.canonical_text, d.decided_by, d.decided_at, d.rationale,
                                           d.alternatives, dtype, d.status, d.authority_flag, d.authority_note,
                                           d.confidence, rids, ev, temp=d.decision_id_temp))
    # last resort for records the model still ignored: a decision straight from the record (recall over elegance)
    for k, alias in enumerate(missing, start=1):
        rec = rec_by_id[r_map[alias]]
        direct = direct_decision(conn, cid, rec).decisions[0]
        direct.temp = f"dr{k}"
        if direct.evidence:
            out.decisions.append(direct)
    kept = {d.temp for d in out.decisions}
    out.edges = [(e.src, e.dst, e.kind, e.scope, e.aspect, e.rationale) for e in res.edges
                 if e.src in kept and e.dst in kept and e.src != e.dst]
    for c in res.conflicts:
        sides = [{"claimant": s.claimant, "claim": s.claim, "evidence": check(s.evidence)} for s in c.sides]
        sides = [s for s in sides if s["evidence"]]
        if len(sides) >= 2:
            out.conflicts.append({"topic": c.topic, "summary": c.summary, "sides": sides})
    # a conflict must show up in the ledger as a contested decision, even if the model left none contested
    if out.conflicts and not any(d.status == "contested" for d in out.decisions):
        for k, c in enumerate(out.conflicts, start=1):
            ev = [e for s in c["sides"] for e in s["evidence"]]
            dates = sorted(_message_date(conn, mid) for mid, _, _ in ev)
            out.decisions.append(DraftDecision(
                cid, c["summary"], [s["claimant"] for s in c["sides"]], dates[-1] if dates else recs[-1]["decision_date"],
                None, [], "explicit", "contested", False, None, 0.5,
                [r["record_id"] for r in recs], ev, temp=f"dc{k}"))
    _fix_statuses(out)
    return out


def _message_date(conn: sqlite3.Connection, mid: str) -> str:
    r = conn.execute("SELECT sent_at, sent_tz FROM emails WHERE message_id=?", (mid,)).fetchone()
    return _local(r["sent_at"], r["sent_tz"]).strftime("%Y-%m-%d") if r else ""


def write_ledger(conn: sqlite3.Connection, outcomes: list[ClusterOutcome]) -> dict:
    """Assign DEC-ids by date across all clusters and replace the ledger tables."""
    for t in ("decisions", "decision_edges", "conflicts", "conflict_sides"):
        conn.execute(f"DELETE FROM {t}")
    conn.execute("DELETE FROM evidence WHERE owner_kind IN ('decision', 'conflict_side')")

    all_d = sorted((d for o in outcomes for d in o.decisions), key=lambda d: (d.decided_at, d.cluster_id, d.temp))
    for i, d in enumerate(all_d, start=1):
        d.final_id = f"DEC-{i:04d}"
        conn.execute("INSERT INTO decisions(decision_id, cluster_id, canonical_text, decided_by, decided_at, rationale,"
                     " alternatives, decision_type, status, authority_flag, authority_note, confidence)"
                     " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                     (d.final_id, d.cluster_id, d.canonical_text, json.dumps(d.decided_by, ensure_ascii=False),
                      d.decided_at, d.rationale, json.dumps(d.alternatives, ensure_ascii=False), d.decision_type,
                      d.status, int(d.authority_flag), d.authority_note, d.confidence))
        for mid, quote, role in d.evidence:
            conn.execute("INSERT INTO evidence(owner_kind, owner_id, message_id, quote, role, verified) "
                         "VALUES('decision',?,?,?,?,1)", (d.final_id, mid, quote, role))

    n_edges = n_conf = 0
    for o in outcomes:
        ids = {d.temp: d.final_id for d in o.decisions}
        for src, dst, kind, scope, aspect, why in o.edges:
            conn.execute("INSERT INTO decision_edges VALUES(?,?,?,?,?,?)", (ids[src], ids[dst], kind, scope, aspect, why))
            n_edges += 1
        for c in o.conflicts:
            n_conf += 1
            cid = f"CON-{n_conf:03d}"
            conn.execute("INSERT INTO conflicts VALUES(?,?,?,?)", (cid, o.cluster_id, c["topic"], c["summary"]))
            for k, s in enumerate(c["sides"]):
                side = chr(ord("A") + k)
                conn.execute("INSERT INTO conflict_sides VALUES(?,?,?,?)", (cid, side, s["claimant"], s["claim"]))
                for mid, quote, role in s["evidence"]:
                    conn.execute("INSERT INTO evidence(owner_kind, owner_id, message_id, quote, role, verified) "
                                 "VALUES('conflict_side',?,?,?,?,1)", (f"{cid}:{side}", mid, quote, role))
        conn.execute("UPDATE clusters SET topic=COALESCE(?, topic), summary=?, current_state=? WHERE cluster_id=?",
                     (o.topic, o.topic, o.current_state, o.cluster_id))
    conn.commit()
    status = {}
    for d in all_d:
        status[d.status] = status.get(d.status, 0) + 1
    return {"decisions": len(all_d), "by_status": status, "edges": n_edges, "conflicts": n_conf,
            "authority_flags": sum(d.authority_flag for d in all_d),
            "non_decision_records": sum(o.non_decisions for o in outcomes)}
