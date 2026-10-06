"""Stage 5: search index (PRD §7 Stage 5).

- passages: each email's new text (and forwarded text) split into <= 120-word passages at paragraph boundaries,
  embedded and full-text indexed (FTS5 / BM25)
- decisions: canonical_text + rationale embedded and full-text indexed
"""
from __future__ import annotations

import re
import sqlite3

import numpy as np

from ..embed import Embedder

MAX_WORDS = 120


def split_passages(text: str, max_words: int = MAX_WORDS) -> list[str]:
    """Greedy pack of paragraphs into <= max_words chunks; long paragraphs split on sentence boundaries.
    Every passage is a verbatim slice of `text` (modulo surrounding whitespace)."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text or "") if p.strip()]
    units: list[str] = []
    for p in paras:
        if len(p.split()) <= max_words:
            units.append(p)
            continue
        sents = re.split(r"(?<=[.!?])\s+", p)
        cur: list[str] = []
        for s in sents:
            if cur and len(" ".join(cur + [s]).split()) > max_words:
                units.append(" ".join(cur))
                cur = []
            cur.append(s)
        if cur:
            units.append(" ".join(cur))
    out: list[str] = []
    cur_p = ""
    for u in units:
        if cur_p and len((cur_p + " " + u).split()) > max_words:
            out.append(cur_p)
            cur_p = u
        else:
            cur_p = f"{cur_p}\n\n{u}" if cur_p else u
    if cur_p:
        out.append(cur_p)
    return out


def run_index(conn: sqlite3.Connection, embedder: Embedder | None = None) -> dict:
    embedder = embedder or Embedder(conn)
    conn.execute("INSERT INTO passages_fts(passages_fts) VALUES('delete-all')")
    conn.execute("DELETE FROM passages")
    rows = []
    for r in conn.execute("SELECT message_id, new_text, fwd_text FROM emails ORDER BY sent_at"):
        for part in (r["new_text"], r["fwd_text"]):
            for p in split_passages(part or ""):
                rows.append((r["message_id"], p))
    vecs = embedder.embed([p for _, p in rows]) if rows else np.zeros((0, 1), dtype=np.float32)
    for (mid, text), v in zip(rows, vecs):
        cur = conn.execute("INSERT INTO passages(message_id, text, embedding) VALUES(?,?,?)",
                           (mid, text, v.astype(np.float32).tobytes()))
        conn.execute("INSERT INTO passages_fts(rowid, text) VALUES(?,?)", (cur.lastrowid, text))

    conn.execute("INSERT INTO decisions_fts(decisions_fts) VALUES('delete-all')")
    decs = conn.execute("SELECT rowid, decision_id, canonical_text, rationale FROM decisions").fetchall()
    dvecs = embedder.embed([f"{d['canonical_text']} {d['rationale'] or ''}".strip() for d in decs]) if decs else []
    for d, v in zip(decs, dvecs):
        conn.execute("UPDATE decisions SET embedding=? WHERE decision_id=?", (v.astype(np.float32).tobytes(), d["decision_id"]))
        conn.execute("INSERT INTO decisions_fts(rowid, canonical_text, rationale) VALUES(?,?,?)",
                     (d["rowid"], d["canonical_text"], d["rationale"] or ""))
    conn.commit()
    return {"passages": len(rows), "decisions": len(decs), "embedder": embedder.name}
