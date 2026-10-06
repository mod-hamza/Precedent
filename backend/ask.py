"""python -m backend.ask "Why did we switch payment providers?"   (needs a built ledger + index)"""
from __future__ import annotations

import asyncio
import json
import sys

from .db import connect
from .embed import Embedder
from .llm import LLM
from .pipeline.ask import ask


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit('usage: python -m backend.ask "question"')
    conn = connect()
    out = asyncio.run(ask(conn, LLM(conn, run_id="cli-ask"), Embedder(conn), " ".join(sys.argv[1:])))
    print(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
