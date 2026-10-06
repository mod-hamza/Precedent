"""Stage 6: ask (PRD §7 Stage 6).

classify (FAST, in parallel with retrieval) -> hybrid retrieval (BM25 + cosine, reciprocal rank fusion) over decisions
and passages -> expand to decision chains, topic current state and conflicts -> answer (ANSWER role) -> verify every
citation in code (one retry with the errors) -> deterministic confidence overlay -> enriched JSON for the UI.
"""
from __future__ import annotations

import asyncio
import json
import re
import sqlite3
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from ..embed import Embedder
from ..llm import LLM
from ..models import Answer, QuestionClass
from .context import _local
from .verify import QuoteStats, verify_quote

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"
ANSWER_PROMPT = (PROMPTS / "answer.md").read_text(encoding="utf-8")
CLASSIFY_PROMPT = (PROMPTS / "classify.md").read_text(encoding="utf-8")
TOP_DECISIONS, TOP_PASSAGES, RRF_K = 8, 12, 60
_STOP = set("""a an the and or but of to in on at by for with from as is are was were be been being do does did have has
had what which who whom whose why how when where whether if then than that this these those it its we our us you your
they their them i me my ever any some there here about into over under after before again ever did decide decided
decision approve approved plan current currently now still""".split())


@dataclass
class Index:
    """In-memory vectors, rebuilt when the ledger changes."""
    stamp: tuple
    dec_ids: list[str]
    dec_vecs: np.ndarray
    pas_ids: list[int]
    pas_vecs: np.ndarray


_INDEX: Index | None = None


def _stamp(conn: sqlite3.Connection) -> tuple:
    return (conn.execute("SELECT COUNT(*), COALESCE(MAX(rowid),0) FROM passages").fetchone()[:],
            conn.execute("SELECT COUNT(*), COALESCE(SUM(LENGTH(canonical_text)),0) FROM decisions").fetchone()[:])


def load_index(conn: sqlite3.Connection) -> Index:
    global _INDEX
    st = _stamp(conn)
    if _INDEX is None or _INDEX.stamp != st:
        drows = conn.execute("SELECT decision_id, embedding FROM decisions WHERE embedding IS NOT NULL").fetchall()
        prows = conn.execute("SELECT id, embedding FROM passages WHERE embedding IS NOT NULL").fetchall()
        dv = np.vstack([np.frombuffer(r[1], dtype=np.float32) for r in drows]) if drows else np.zeros((0, 1), np.float32)
        pv = np.vstack([np.frombuffer(r[1], dtype=np.float32) for r in prows]) if prows else np.zeros((0, 1), np.float32)
        _INDEX = Index(st, [r[0] for r in drows], dv, [r[0] for r in prows], pv)
    return _INDEX


def _fts_query(text: str) -> str:
    toks = [t for t in re.findall(r"[\w€%]+", text.casefold()) if len(t) >= 3 and t not in _STOP]
    return " OR ".join(f'"{t}"' for t in dict.fromkeys(toks))


def _rrf(*rankings: list) -> list:
    score: dict = defaultdict(float)
    for ranking in rankings:
        for rank, key in enumerate(ranking):
            score[key] += 1.0 / (RRF_K + rank + 1)
    return sorted(score, key=lambda k: -score[k])


def retrieve(conn: sqlite3.Connection, embedder: Embedder, question: str) -> tuple[list[str], list[int]]:
    idx = load_index(conn)
    q = _fts_query(question)
    bm_d = [r[0] for r in conn.execute(
        "SELECT d.decision_id FROM decisions_fts f JOIN decisions d ON d.rowid=f.rowid WHERE decisions_fts MATCH ? "
        "ORDER BY bm25(decisions_fts) LIMIT 30", (q,))] if q else []
    bm_p = [r[0] for r in conn.execute(
        "SELECT rowid FROM passages_fts WHERE passages_fts MATCH ? ORDER BY bm25(passages_fts) LIMIT 40", (q,))] if q else []
    qv = embedder.embed([question])[0]
    vec_d = [idx.dec_ids[i] for i in np.argsort(-(idx.dec_vecs @ qv))[:30]] if len(idx.dec_ids) else []
    vec_p = [idx.pas_ids[i] for i in np.argsort(-(idx.pas_vecs @ qv))[:40]] if len(idx.pas_ids) else []
    return _rrf(bm_d, vec_d)[:TOP_DECISIONS], _rrf(bm_p, vec_p)[:TOP_PASSAGES]


def chain(conn: sqlite3.Connection, seeds: list[str]) -> list[str]:
    """All decisions connected to the seeds through lifecycle edges (ancestors and descendants)."""
    adj = defaultdict(set)
    for s, d in conn.execute("SELECT src, dst FROM decision_edges"):
        adj[s].add(d)
        adj[d].add(s)
    seen, todo = set(seeds), list(seeds)
    while todo:
        for n in adj[todo.pop()]:
            if n not in seen:
                seen.add(n)
                todo.append(n)
    return list(seen)


class _Aliases:
    def __init__(self) -> None:
        self.by_mid: dict[str, str] = {}

    def __call__(self, mid: str) -> str:
        if mid not in self.by_mid:
            self.by_mid[mid] = f"e{len(self.by_mid) + 1}"
        return self.by_mid[mid]

    def reverse(self) -> dict[str, str]:
        return {v: k for k, v in self.by_mid.items()}


def _email_meta(conn: sqlite3.Connection, mid: str) -> dict:
    r = conn.execute("SELECT e.*, p.canonical_name FROM emails e LEFT JOIN people p ON p.id=e.from_person_id "
                     "WHERE message_id=?", (mid,)).fetchone()
    if r is None:
        return {"message_id": mid}
    return {"message_id": mid, "sender": r["canonical_name"] or r["from_name"] or r["from_addr"],
            "date": _local(r["sent_at"], r["sent_tz"]).strftime("%Y-%m-%d"), "subject": r["subject"],
            "new_text": r["new_text"] or "", "fwd_text": r["fwd_text"] or ""}


def build_context(conn: sqlite3.Connection, dec_ids: list[str], pas_ids: list[int], qc: QuestionClass | None
                  ) -> tuple[str, _Aliases, list[str]]:
    alias = _Aliases()
    all_ids = chain(conn, dec_ids)
    decs = {r["decision_id"]: r for r in conn.execute(
        f"SELECT * FROM decisions WHERE decision_id IN ({','.join('?' * len(all_ids))})", all_ids)} if all_ids else {}
    order = sorted(decs, key=lambda d: (decs[d]["cluster_id"], decs[d]["decided_at"]))
    edges = conn.execute("SELECT * FROM decision_edges").fetchall()
    as_of = qc.as_of_date if qc and qc.type == "as_of" else None
    out = []
    if as_of:
        out.append(f"QUESTION IS ABOUT THE STATE AS OF {as_of}. Decisions dated after it had not happened yet.\n")
    out.append("DECISION LEDGER ENTRIES")
    clusters = []
    for did in order:
        d = decs[did]
        if d["cluster_id"] not in clusters:
            clusters.append(d["cluster_id"])
        line = (f"\n[{did}] status={d['status']}  decided {d['decided_at']} by {', '.join(json.loads(d['decided_by'] or '[]'))}"
                f"  ({d['decision_type']})")
        if as_of and d["decided_at"] > as_of:
            line += "  [AFTER THE AS-OF DATE]"
        out.append(line)
        out.append(f"  decision: {d['canonical_text']}")
        if d["rationale"]:
            out.append(f"  rationale: {d['rationale']}")
        alts = json.loads(d["alternatives"] or "[]")
        if alts:
            out.append(f"  alternatives considered: {'; '.join(alts)}")
        if d["authority_flag"]:
            out.append(f"  AUTHORITY FLAG: {d['authority_note']}")
        for e in edges:
            if e["src"] == did and e["dst"] in decs:
                out.append(f"  {e['kind']} {e['dst']}" + (f" (changed: {e['aspect']})" if e["aspect"] else ""))
            if e["dst"] == did and e["src"] in decs:
                out.append(f"  was {e['kind'].replace('supersedes', 'superseded').replace('amends', 'amended').replace('refines', 'refined')}"
                           f" by {e['src']} on {decs[e['src']]['decided_at']}")
        for ev in conn.execute("SELECT * FROM evidence WHERE owner_kind='decision' AND owner_id=? ORDER BY id", (did,)):
            m = _email_meta(conn, ev["message_id"])
            out.append(f"  evidence [{alias(ev['message_id'])}] {m.get('sender')}, {m.get('date')} ({ev['role']}): \"{ev['quote']}\"")
    for cid in clusters:
        c = conn.execute("SELECT topic, current_state FROM clusters WHERE cluster_id=?", (cid,)).fetchone()
        if c and c["current_state"]:
            out.append(f"\nTOPIC '{c['topic']}' CURRENT STATE: {c['current_state']}")
        for con in conn.execute("SELECT * FROM conflicts WHERE cluster_id=?", (cid,)):
            out.append(f"\nCONFLICT on '{con['topic']}': {con['summary']}")
            for s in conn.execute("SELECT * FROM conflict_sides WHERE conflict_id=? ORDER BY side", (con["conflict_id"],)):
                out.append(f"  version {s['side']} ({s['claimant']}): {s['claim']}")
                for ev in conn.execute("SELECT * FROM evidence WHERE owner_kind='conflict_side' AND owner_id=?",
                                       (f"{con['conflict_id']}:{s['side']}",)):
                    out.append(f"    evidence [{alias(ev['message_id'])}]: \"{ev['quote']}\"")
    if not decs:
        out.append("(no ledger entries matched this question)")
    out.append("\nEMAIL PASSAGES")
    for pid in pas_ids:
        p = conn.execute("SELECT message_id, text FROM passages WHERE id=?", (pid,)).fetchone()
        if p is None:
            continue
        m = _email_meta(conn, p["message_id"])
        out.append(f"\n[{alias(p['message_id'])}] {m.get('date')} {m.get('sender')}, subject {m.get('subject')!r}:\n{p['text']}")
    return "\n".join(out), alias, list(decs)


def check_answer(ans: Answer, texts: dict[str, tuple[str, str]], rev: dict[str, str], known_decisions: set[str]
                 ) -> tuple[list[dict], list[str]]:
    """Verify citations; returns (verified citations with real message ids, error strings)."""
    errors, cites = [], []
    stats = QuoteStats()
    markers = {int(n) for n in re.findall(r"\[\^(\d+)\]", ans.answer_md)}
    numbers = {c.n for c in ans.citations}
    for n in sorted(markers - numbers):
        errors.append(f"marker [^{n}] has no citation")
    for c in ans.citations:
        mid = rev.get(c.message_id.strip("[] "), c.message_id)
        q = verify_quote(mid, c.quote, "citation", texts, stats)
        if q.verified:
            cites.append({"n": c.n, "message_id": q.message_id, "quote": q.quote})
        else:
            errors.append(f"citation [^{c.n}] quote is not verbatim in {c.message_id}: {c.quote[:80]!r}")
    for d in ans.decision_ids:
        if d not in known_decisions:
            errors.append(f"unknown decision id {d}")
    return cites, errors


def confidence(conn: sqlite3.Connection, ans: Answer, cites: list[dict], errors: list[str]) -> str:
    """PRD §7.6 step 5: high = explicit decision, final, >= 2 verified quotes from >= 2 messages; medium = implicit or
    single source; low = verification failures or partial."""
    if errors or ans.status == "partial":
        return "low"
    if ans.status == "no_decision":
        return "medium" if ans.closest or cites else "low"
    types = [r[0] for r in conn.execute(
        f"SELECT decision_type FROM decisions WHERE decision_id IN ({','.join('?' * len(ans.decision_ids))})",
        ans.decision_ids)] if ans.decision_ids else []
    explicit = bool(types) and all(t == "explicit" for t in types)
    if explicit and len(cites) >= 2 and len({c["message_id"] for c in cites}) >= 2 and ans.status in ("found", "contested"):
        return "high"
    return "medium"


async def ask(conn: sqlite3.Connection, llm: LLM, embedder: Embedder, question: str) -> dict:
    t0 = time.perf_counter()
    loop = asyncio.get_running_loop()
    qc_task = asyncio.create_task(llm.structured("FAST", CLASSIFY_PROMPT, question, QuestionClass, stage="classify"))
    dec_ids, pas_ids = await loop.run_in_executor(None, retrieve, conn, embedder, question)
    try:
        qc = await qc_task
    except Exception:  # classification only refines the context; never fail the answer on it
        qc = None
    ctx, alias, known = build_context(conn, dec_ids, pas_ids, qc)
    user = f"QUESTION: {question}\n\nCONTEXT\n{ctx}"
    rev = alias.reverse()
    texts = {mid: (m.get("new_text", ""), m.get("fwd_text", "")) for mid in rev.values()
             for m in [_email_meta(conn, mid)]}

    ans = await llm.structured("ANSWER", ANSWER_PROMPT, user, Answer, stage="answer")
    cites, errors = check_answer(ans, texts, rev, set(known))
    if errors:
        retry = (user + "\n\nYOUR PREVIOUS ANSWER HAD THESE PROBLEMS; fix them (quotes must be copied exactly from the "
                 "context):\n- " + "\n- ".join(errors))
        ans2 = await llm.structured("ANSWER", ANSWER_PROMPT, retry, Answer, stage="answer_retry")
        cites2, errors2 = check_answer(ans2, texts, rev, set(known))
        if len(errors2) <= len(errors):
            ans, cites, errors = ans2, cites2, errors2
    caveats = list(ans.caveats)
    if errors:
        caveats.append("Some citations could not be verified against the emails and were removed.")
    conf = confidence(conn, ans, cites, errors)

    cite_meta = []
    for c in cites:
        m = _email_meta(conn, c["message_id"])
        cite_meta.append({**c, "sender": m.get("sender"), "date": m.get("date"), "subject": m.get("subject")})
    closest = []
    for c in ans.closest:
        mid = rev.get(c.message_id.strip("[] "), c.message_id)
        m = _email_meta(conn, mid)
        if "sender" in m:
            closest.append({"message_id": mid, "why": c.why, "sender": m["sender"], "date": m["date"],
                            "subject": m["subject"]})
    used = [dict(r) for r in conn.execute(
        f"SELECT decision_id, canonical_text, status, decided_at, decision_type, authority_flag FROM decisions "
        f"WHERE decision_id IN ({','.join('?' * len(ans.decision_ids))})", ans.decision_ids)] if ans.decision_ids else []
    latency = int((time.perf_counter() - t0) * 1000)
    result = {"question": question, "status": ans.status, "answer_md": ans.answer_md, "citations": cite_meta,
              "decision_ids": [d["decision_id"] for d in used], "decisions": used, "confidence": conf,
              "model_confidence": ans.confidence, "caveats": caveats, "closest": closest,
              "question_type": qc.type if qc else None, "verification_errors": errors, "latency_ms": latency}
    conn.execute("INSERT INTO qa_log(question, answer_json, latency_ms, created_at) VALUES(?,?,?,?)",
                 (question, json.dumps(result, ensure_ascii=False), latency, datetime.now(timezone.utc).isoformat()))
    conn.commit()
    return result
