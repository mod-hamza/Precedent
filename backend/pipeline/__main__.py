"""python -m backend.pipeline [--stages triage,extract] [--thread T-...] [--limit N]

Assumes Stage 0 has run (python -m backend.ingest).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

from ..db import connect
from .context import thread_ids
from .run import STAGES, run_pipeline


def main() -> None:
    ap = argparse.ArgumentParser(description="Run pipeline stages over the ingested mailbox")
    ap.add_argument("--stages", default="triage,extract")
    ap.add_argument("--thread", action="append", help="restrict to these thread ids (repeatable)")
    ap.add_argument("--limit", type=int, help="first N threads only (smoke runs)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    stages = [s.strip() for s in args.stages.split(",") if s.strip()]
    unknown = [s for s in stages if s not in STAGES]
    if unknown:
        sys.exit(f"unknown stage(s) {unknown}; available: {list(STAGES)}")
    conn = connect()
    tids = args.thread or thread_ids(conn)
    if args.limit:
        tids = tids[:args.limit]

    def emit(e: dict) -> None:
        if args.quiet:
            return
        if e["event"] == "progress":
            if e["done"] == e["total"] or e["done"] % 25 == 0:
                print(f"  {e['stage']}: {e['done']}/{e['total']}", flush=True)
        elif e["event"] == "decision_found":
            print(f"  + {e['date']}  {e['text'][:100]}", flush=True)
        elif e["event"] == "stage_start":
            print(f"[{e['stage']}]", flush=True)

    out = asyncio.run(run_pipeline(conn, stages, threads=tids, emit=emit))
    print(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
