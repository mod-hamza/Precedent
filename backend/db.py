"""SQLite schema (PRD §6) and connection helper."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from .config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS emails(
  id INTEGER PRIMARY KEY,
  message_id TEXT UNIQUE NOT NULL,
  thread_id TEXT, in_reply_to TEXT, refs TEXT,
  from_person_id INTEGER, from_addr TEXT, from_name TEXT,
  to_addrs TEXT, cc_addrs TEXT,
  sent_at TEXT NOT NULL,
  sent_tz TEXT,
  subject TEXT,
  new_text TEXT,
  quoted_text TEXT,
  fwd_text TEXT,
  fwd_meta TEXT,
  body_raw TEXT,
  attachment_names TEXT,
  source_file TEXT
);
CREATE INDEX IF NOT EXISTS emails_thread ON emails(thread_id, sent_at);

CREATE TABLE IF NOT EXISTS people(id INTEGER PRIMARY KEY, canonical_name TEXT, role_guess TEXT, org TEXT, is_internal INT);
CREATE TABLE IF NOT EXISTS identities(id INTEGER PRIMARY KEY, person_id INT, kind TEXT, value TEXT, UNIQUE(kind, value));
CREATE TABLE IF NOT EXISTS threads(thread_id TEXT PRIMARY KEY, subject_norm TEXT, first_at TEXT, last_at TEXT,
  n_msgs INT, participants TEXT);
CREATE TABLE IF NOT EXISTS triage(thread_id TEXT, message_id TEXT, signal TEXT, note TEXT, PRIMARY KEY(thread_id, message_id));
CREATE TABLE IF NOT EXISTS thread_triage(thread_id TEXT PRIMARY KEY, has_candidate INT);

CREATE TABLE IF NOT EXISTS records(
  record_id TEXT PRIMARY KEY, thread_id TEXT, topic_label TEXT, decision_text TEXT,
  stance TEXT, decision_type TEXT, decided_by TEXT, decision_date TEXT,
  rationale TEXT, alternatives TEXT, conditions TEXT, overrides_hint TEXT,
  authority_note TEXT, confidence REAL, embedding BLOB, cluster_id TEXT
);
CREATE TABLE IF NOT EXISTS evidence(
  id INTEGER PRIMARY KEY, owner_kind TEXT, owner_id TEXT, message_id TEXT, quote TEXT, role TEXT, verified INT
);
CREATE INDEX IF NOT EXISTS evidence_owner ON evidence(owner_kind, owner_id);
CREATE TABLE IF NOT EXISTS clusters(cluster_id TEXT PRIMARY KEY, topic TEXT, summary TEXT, current_state TEXT, n_records INT);
CREATE TABLE IF NOT EXISTS decisions(
  decision_id TEXT PRIMARY KEY, cluster_id TEXT, canonical_text TEXT, decided_by TEXT, decided_at TEXT,
  rationale TEXT, alternatives TEXT, decision_type TEXT,
  status TEXT,
  authority_flag INT, authority_note TEXT, confidence REAL, embedding BLOB
);
CREATE TABLE IF NOT EXISTS decision_edges(src TEXT, dst TEXT, kind TEXT, scope TEXT, aspect TEXT, rationale TEXT);
CREATE TABLE IF NOT EXISTS conflicts(conflict_id TEXT PRIMARY KEY, cluster_id TEXT, topic TEXT, summary TEXT);
CREATE TABLE IF NOT EXISTS conflict_sides(conflict_id TEXT, side TEXT, claimant TEXT, claim TEXT);
CREATE TABLE IF NOT EXISTS passages(id INTEGER PRIMARY KEY, message_id TEXT, text TEXT, embedding BLOB);
CREATE VIRTUAL TABLE IF NOT EXISTS passages_fts USING fts5(text, content='passages', content_rowid='id');
CREATE VIRTUAL TABLE IF NOT EXISTS decisions_fts USING fts5(canonical_text, rationale, content='decisions');
CREATE TABLE IF NOT EXISTS qa_log(id INTEGER PRIMARY KEY, question TEXT, answer_json TEXT, latency_ms INT, created_at TEXT);
CREATE TABLE IF NOT EXISTS runs(run_id TEXT, stage TEXT, started_at TEXT, finished_at TEXT, n_in INT, n_out INT,
  tokens_in INT, tokens_out INT, cost_usd REAL, notes TEXT);
CREATE TABLE IF NOT EXISTS feedback(id INTEGER PRIMARY KEY, decision_id TEXT, kind TEXT, note TEXT, created_at TEXT);

-- LLM response cache keyed on sha256(model + prompt + schema); makes re-runs free and demos reproducible.
CREATE TABLE IF NOT EXISTS llm_cache(key TEXT PRIMARY KEY, model TEXT, response TEXT, tokens_in INT, tokens_out INT,
  created_at TEXT);
-- One row per logical call (cached or not), for the per-stage cost panel.
CREATE TABLE IF NOT EXISTS llm_calls(id INTEGER PRIMARY KEY, run_id TEXT, stage TEXT, model TEXT, cached INT,
  tokens_in INT, tokens_out INT, cost_usd REAL, latency_ms INT, created_at TEXT);
"""


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(path or settings.db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    return conn
