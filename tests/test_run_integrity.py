"""Integrity of an actual pipeline run (PRD §16: quote validity 100%, proven by a test).

Runs against the demo snapshot if present, else the working DB; skipped when neither has a ledger.
"""
import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CANDIDATES = [ROOT / "demo" / "cached_run.sqlite", ROOT / "data" / "precedent.db"]


def _db():
    for p in CANDIDATES:
        if p.exists():
            conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
            try:
                if conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]:
                    return conn
            except sqlite3.DatabaseError:
                pass
    pytest.skip("no pipeline run available")


def test_every_shown_quote_is_verbatim():
    conn = _db()
    rows = conn.execute("SELECT ev.owner_kind, ev.owner_id, ev.quote, e.new_text, e.fwd_text FROM evidence ev "
                        "JOIN emails e USING(message_id) WHERE ev.verified=1").fetchall()
    assert rows
    bad = [(k, o, q[:60]) for k, o, q, n, f in rows if not (q in (n or "") or q in (f or ""))]
    assert bad == []


def test_every_decision_has_verified_evidence():
    conn = _db()
    orphans = conn.execute("SELECT decision_id FROM decisions d WHERE NOT EXISTS (SELECT 1 FROM evidence ev "
                           "WHERE ev.owner_kind='decision' AND ev.owner_id=d.decision_id AND ev.verified=1)").fetchall()
    assert orphans == []


def test_edges_point_newer_to_older_between_existing_decisions():
    conn = _db()
    dates = dict(conn.execute("SELECT decision_id, decided_at FROM decisions").fetchall())
    for src, dst in conn.execute("SELECT src, dst FROM decision_edges"):
        assert src in dates and dst in dates
        assert dates[src] >= dates[dst], (src, dst)
