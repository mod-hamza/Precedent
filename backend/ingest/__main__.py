"""python -m backend.ingest [paths...] [--no-llm]   (defaults to the configured corpus directory)"""
from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from pathlib import Path

from ..config import settings
from ..db import connect
from ..llm import LLM
from . import run_stage0


def main() -> None:
    ap = argparse.ArgumentParser(description="Stage 0: parse, thread and resolve identities")
    ap.add_argument("paths", nargs="*", type=Path, default=[settings.corpus_dir])
    ap.add_argument("--no-llm", action="store_true", help="skip FAST identity adjudication (exact-name fallback)")
    args = ap.parse_args()

    conn = connect()
    run_id = "run-" + uuid.uuid4().hex[:8]
    llm = None if args.no_llm else LLM(conn, run_id=run_id)
    stats = asyncio.run(run_stage0(conn, args.paths, llm=llm, run_id=run_id))
    print(json.dumps({"run_id": run_id, **stats}, indent=1))


if __name__ == "__main__":
    main()
