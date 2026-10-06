"""Demo mode tooling (PRD §7 G7 / §16).

python -m backend.demo snapshot     copy the current DB (ledger + LLM cache + embedding cache) to demo/cached_run.sqlite
python -m backend.demo warm         ask the suggested + Q&A questions once so demo mode can answer them offline
python -m backend.demo serve        load the snapshot into the active DB and start the API in offline demo mode

Demo mode never calls a model: any question that was asked before the snapshot is answered from the cache, and the
UI shows a clear message for anything else.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import sys

from .config import ROOT, settings
from .db import connect

DEMO_DB = ROOT / "demo" / "cached_run.sqlite"
SUGGESTED = ROOT / "demo" / "suggested_questions.json"


def snapshot() -> None:
    DEMO_DB.parent.mkdir(parents=True, exist_ok=True)
    src = connect()
    src.execute("DELETE FROM qa_log")  # keep the snapshot about the ledger, not about who asked what
    src.commit()
    if DEMO_DB.exists():
        DEMO_DB.unlink()
    dst = sqlite3.connect(DEMO_DB)
    src.backup(dst)
    dst.execute("PRAGMA journal_mode=DELETE")
    dst.execute("VACUUM")
    dst.close()
    print(f"wrote {DEMO_DB} ({DEMO_DB.stat().st_size / 1e6:.1f} MB)")


def warm(extra: list[str] | None = None) -> None:
    from .embed import Embedder
    from .llm import LLM
    from .pipeline.ask import ask

    qs = json.loads(SUGGESTED.read_text(encoding="utf-8")) if SUGGESTED.exists() else []
    qs += extra or []
    conn = connect()
    emb = Embedder(conn)
    for q in dict.fromkeys(qs):
        a = asyncio.run(ask(conn, LLM(conn, run_id="demo-warm"), emb, q))
        print(f"{a['status']:12} {a['confidence']:6} {a['latency_ms']:6} ms  {q}")


def serve() -> None:
    if not DEMO_DB.exists():
        sys.exit("no snapshot: run python -m backend.demo snapshot first")
    conn = connect()
    src = sqlite3.connect(DEMO_DB)
    src.backup(conn)
    src.close()
    conn.close()
    from . import app as app_mod
    from . import llm as llm_mod
    # settings were read at import time, so switch the running app into demo mode explicitly
    app_mod.STATE["demo_mode"] = True
    llm_mod.RUNTIME["offline"] = True
    app_mod.main()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "snapshot":
        snapshot()
    elif cmd == "warm":
        warm(sys.argv[2:])
    elif cmd == "serve":
        serve()
    else:
        sys.exit(__doc__)
