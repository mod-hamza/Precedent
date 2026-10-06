"""Content-addressed LLM response cache stored in the main SQLite DB."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any


def cache_key(**parts: Any) -> str:
    blob = json.dumps(parts, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class LLMCache:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.lock = threading.Lock()

    def get(self, key: str) -> sqlite3.Row | None:
        with self.lock:
            return self.conn.execute("SELECT * FROM llm_cache WHERE key=?", (key,)).fetchone()

    def put(self, key: str, model: str, response: str, tokens_in: int, tokens_out: int) -> None:
        with self.lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO llm_cache(key, model, response, tokens_in, tokens_out, created_at) VALUES(?,?,?,?,?,?)",
                (key, model, response, tokens_in, tokens_out, datetime.now(timezone.utc).isoformat()),
            )
            self.conn.commit()

    def log_call(self, run_id: str | None, stage: str, model: str, cached: bool, tokens_in: int, tokens_out: int,
                 cost_usd: float, latency_ms: int) -> None:
        with self.lock:
            self.conn.execute(
                "INSERT INTO llm_calls(run_id, stage, model, cached, tokens_in, tokens_out, cost_usd, latency_ms, created_at)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                (run_id, stage, model, int(cached), tokens_in, tokens_out, cost_usd, latency_ms,
                 datetime.now(timezone.utc).isoformat()),
            )
            self.conn.commit()
