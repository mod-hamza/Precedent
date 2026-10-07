"""FastAPI server: the API contract in PRD §8, plus the built frontend (frontend/dist) as static files.

uvicorn backend.app:app --port 8000        (or: python -m backend.app)
Every GET accepts ?redact=1 to mask emails / phone numbers / IBANs in the response (PRD §10.6).
"""
from __future__ import annotations

import asyncio
import json
import shutil
import sqlite3
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import llm as llm_mod
from .config import ROOT, settings
from .db import connect
from .embed import Embedder
from .ingest import run_stage0
from .llm import LLM, LLMOffline
from .pipeline.ask import ask as ask_question
from .pipeline.ask import chain, load_index
from .pipeline.context import _local
from .pipeline.run import run_pipeline
from .render import redact

DEMO_DB = ROOT / "demo" / "cached_run.sqlite"
EVAL_EXPORT = ROOT / "eval" / "results" / "eval_results.json"
UPLOADS = ROOT / "data" / "uploads"
PIPELINE_STAGES = ["triage", "extract", "cluster", "reconcile", "index"]
DERIVED_TABLES = ["triage", "thread_triage", "records", "evidence", "clusters", "decisions", "decision_edges",
                  "conflicts", "conflict_sides", "passages", "qa_log", "feedback"]

CONN = connect()
_EMBEDDER: Embedder | None = None
RUNS: dict[str, dict] = {}  # run_id -> {"status", "events": [...], "subscribers": [queues]}
STATE = {"demo_mode": settings.offline}
llm_mod.RUNTIME["offline"] = settings.offline


def embedder() -> Embedder:
    global _EMBEDDER
    if _EMBEDDER is None:
        _EMBEDDER = Embedder(CONN)
    return _EMBEDDER


def _warm_up() -> None:
    # the sentence-transformers model loads lazily inside embed(); pay that cost at startup, not on the first ask
    try:
        embedder().embed(["warm up"])
        load_index(CONN)
    except Exception:
        pass


@asynccontextmanager
async def _lifespan(_: FastAPI):
    threading.Thread(target=_warm_up, name="warmup", daemon=True).start()
    yield


app = FastAPI(title="Precedent", version="1.0", lifespan=_lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def out(request: Request, payload: Any) -> JSONResponse:
    if request.query_params.get("redact") in ("1", "true"):
        payload = redact(payload)
    return JSONResponse(payload)


def rows(sql: str, args: tuple | list = ()) -> list[dict]:
    return [dict(r) for r in CONN.execute(sql, args)]


def _j(v: str | None, default: Any) -> Any:
    try:
        return json.loads(v) if v else default
    except (TypeError, ValueError):
        return default


# ------------------------------------------------------------------ helpers
def email_card(mid: str) -> dict | None:
    r = CONN.execute("SELECT e.*, p.canonical_name, p.role_guess FROM emails e LEFT JOIN people p "
                     "ON p.id=e.from_person_id WHERE message_id=?", (mid,)).fetchone()
    if r is None:
        return None
    return {"message_id": mid, "thread_id": r["thread_id"], "subject": r["subject"],
            "sender": r["canonical_name"] or r["from_name"], "sender_addr": r["from_addr"], "sender_role": r["role_guess"],
            "date": _local(r["sent_at"], r["sent_tz"]).strftime("%Y-%m-%d %H:%M"), "sent_at": r["sent_at"],
            "to": _j(r["to_addrs"], []), "cc": _j(r["cc_addrs"], [])}


def evidence_for(kind: str, owner: str) -> list[dict]:
    out_ = []
    for e in CONN.execute("SELECT * FROM evidence WHERE owner_kind=? AND owner_id=? AND verified=1 ORDER BY id",
                          (kind, owner)):
        card = email_card(e["message_id"]) or {"message_id": e["message_id"]}
        r = CONN.execute("SELECT fwd_text, fwd_meta FROM emails WHERE message_id=?", (e["message_id"],)).fetchone()
        forwarded = bool(r and r["fwd_text"] and e["quote"] in r["fwd_text"])
        item = {**card, "quote": e["quote"], "role": e["role"], "forwarded": forwarded}
        if forwarded:  # attribute forwarded evidence to the original author and date
            meta = _j(r["fwd_meta"], {})
            item["original_author"] = meta.get("from_name") or meta.get("from_addr")
            item["original_date"] = (meta.get("date") or "")[:10] or None
        out_.append(item)
    return out_


def decision_summary(d: sqlite3.Row | dict) -> dict:
    d = dict(d)
    threads = {CONN.execute("SELECT thread_id FROM emails WHERE message_id=?", (m,)).fetchone()[0]
               for (m,) in CONN.execute("SELECT DISTINCT message_id FROM evidence WHERE owner_kind='decision' "
                                        "AND owner_id=?", (d["decision_id"],))}
    return {"decision_id": d["decision_id"], "cluster_id": d["cluster_id"], "text": d["canonical_text"],
            "decided_by": _j(d["decided_by"], []), "decided_at": d["decided_at"], "status": d["status"],
            "decision_type": d["decision_type"], "authority_flag": bool(d["authority_flag"]),
            "cross_thread": len(threads) > 1, "confidence": d["confidence"]}


def decision_confidence(d: dict, ev: list[dict]) -> dict:
    """Deterministic label shown in the drawer footer (same rule as Ask)."""
    msgs = {e["message_id"] for e in ev}
    if d["decision_type"] == "explicit" and len(ev) >= 2 and len(msgs) >= 2:
        return {"label": "high", "why": f"Explicit decision backed by {len(ev)} verified quotes from {len(msgs)} emails."}
    if d["decision_type"] == "implicit":
        return {"label": "medium", "why": "Implicit decision (closed by an informal reply); read the evidence."}
    return {"label": "medium", "why": f"Backed by {len(ev)} verified quote(s) from {len(msgs)} email(s)."}


# ------------------------------------------------------------------ read endpoints
@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "demo_mode": STATE["demo_mode"], "provider": settings.provider,
            "models": {r: settings.role(r).model for r in ("FAST", "CORE", "REASON", "ANSWER")}}


@app.get("/api/stats")
def stats(request: Request) -> JSONResponse:
    one = lambda sql: CONN.execute(sql).fetchone()[0]
    by_status = {r["status"]: r["n"] for r in rows("SELECT status, COUNT(*) n FROM decisions GROUP BY status")}
    q = {"quotes_total": 0, "quotes_snapped": 0, "quotes_dropped": 0}
    for stage in ("extract", "reconcile"):
        r = CONN.execute("SELECT notes FROM runs WHERE stage=? ORDER BY finished_at DESC LIMIT 1", (stage,)).fetchone()
        n = _j(r["notes"], {}) if r else {}
        for k in q:
            q[k] += n.get(k, 0)
    ev = CONN.execute("SELECT COUNT(*), COALESCE(SUM(verified),0) FROM evidence WHERE owner_kind='decision'").fetchone()
    stage_rows = rows("SELECT stage, MAX(finished_at) finished_at, notes FROM runs GROUP BY stage")
    seconds = {r["stage"]: _j(r["notes"], {}).get("seconds") for r in stage_rows}
    usage = rows("SELECT stage, COUNT(*) calls, SUM(tokens_in) tokens_in, SUM(tokens_out) tokens_out, "
                 "ROUND(SUM(cost_usd), 4) cost_usd FROM llm_calls WHERE cached=0 GROUP BY stage")
    threads = one("SELECT COUNT(*) FROM threads")
    cands = one("SELECT COUNT(*) FROM thread_triage WHERE has_candidate=1")
    return out(request, {
        "emails": one("SELECT COUNT(*) FROM emails"), "threads": threads, "people": one("SELECT COUNT(*) FROM people"),
        "candidate_threads": cands, "filtered_pct": round(100 * (1 - cands / threads), 1) if threads else 0,
        "records": one("SELECT COUNT(*) FROM records"), "decisions": sum(by_status.values()),
        "decisions_by_status": by_status, "conflicts": one("SELECT COUNT(*) FROM conflicts"),
        "authority_flags": one("SELECT COUNT(*) FROM decisions WHERE authority_flag=1"),
        "implicit": one("SELECT COUNT(*) FROM decisions WHERE decision_type='implicit'"),
        **q, "evidence_verified_ratio": round(ev[1] / ev[0], 3) if ev[0] else 1.0,
        "stage_seconds": seconds, "usage_by_stage": usage, "demo_mode": STATE["demo_mode"],
    })


@app.get("/api/decisions")
def list_decisions(request: Request, status: str | None = None, q: str | None = None, cluster: str | None = None,
                   from_: str | None = Query(None, alias="from"), to: str | None = None,
                   type: str | None = None) -> JSONResponse:
    sql, args = "SELECT * FROM decisions WHERE 1=1", []
    if status:
        sql += f" AND status IN ({','.join('?' * len(status.split(',')))})"
        args += status.split(",")
    if cluster:
        sql += " AND cluster_id=?"
        args.append(cluster)
    if type:
        sql += " AND decision_type=?"
        args.append(type)
    if from_:
        sql += " AND decided_at>=?"
        args.append(from_)
    if to:
        sql += " AND decided_at<=?"
        args.append(to)
    if q:
        sql += " AND (canonical_text LIKE ? OR rationale LIKE ?)"
        args += [f"%{q}%", f"%{q}%"]
    return out(request, [decision_summary(d) for d in CONN.execute(sql + " ORDER BY decided_at, decision_id", args)])


@app.get("/api/decisions/{decision_id}")
def get_decision(request: Request, decision_id: str) -> JSONResponse:
    d = CONN.execute("SELECT * FROM decisions WHERE decision_id=?", (decision_id,)).fetchone()
    if d is None:
        raise HTTPException(404, "decision not found")
    ids = chain(CONN, [decision_id])
    hist = rows(f"SELECT decision_id, canonical_text text, decided_at, status FROM decisions "
                f"WHERE decision_id IN ({','.join('?' * len(ids))}) ORDER BY decided_at", ids)
    edges = rows(f"SELECT * FROM decision_edges WHERE src IN ({','.join('?' * len(ids))}) "
                 f"OR dst IN ({','.join('?' * len(ids))})", ids + ids)
    ev = evidence_for("decision", decision_id)
    cl = CONN.execute("SELECT topic, current_state FROM clusters WHERE cluster_id=?", (d["cluster_id"],)).fetchone()
    conflicts = [c["conflict_id"] for c in rows("SELECT conflict_id FROM conflicts WHERE cluster_id=?", (d["cluster_id"],))]
    body = {**decision_summary(d), "rationale": d["rationale"], "alternatives": _j(d["alternatives"], []),
            "authority_note": d["authority_note"], "evidence": ev, "history": hist, "edges": edges,
            "topic": cl["topic"] if cl else None, "current_state": cl["current_state"] if cl else None,
            "conflict_ids": conflicts, "confidence_label": decision_confidence(dict(d), ev)}
    return out(request, body)


@app.get("/api/clusters")
def list_clusters(request: Request) -> JSONResponse:
    res = []
    for c in CONN.execute("SELECT * FROM clusters ORDER BY cluster_id"):
        decs = rows("SELECT decision_id, status, decided_at FROM decisions WHERE cluster_id=? ORDER BY decided_at",
                    (c["cluster_id"],))
        if not decs:
            continue
        res.append({"cluster_id": c["cluster_id"], "topic": c["topic"], "current_state": c["current_state"],
                    "n_decisions": len(decs), "first_at": decs[0]["decided_at"], "last_at": decs[-1]["decided_at"],
                    "statuses": sorted({x["status"] for x in decs})})
    return out(request, sorted(res, key=lambda x: x["first_at"]))


@app.get("/api/clusters/{cluster_id}")
def get_cluster(request: Request, cluster_id: str) -> JSONResponse:
    c = CONN.execute("SELECT * FROM clusters WHERE cluster_id=?", (cluster_id,)).fetchone()
    if c is None:
        raise HTTPException(404, "cluster not found")
    decs = [decision_summary(d) for d in CONN.execute(
        "SELECT * FROM decisions WHERE cluster_id=? ORDER BY decided_at", (cluster_id,))]
    ids = [d["decision_id"] for d in decs]
    edges = rows(f"SELECT * FROM decision_edges WHERE src IN ({','.join('?' * len(ids))})", ids) if ids else []
    return out(request, {"cluster_id": cluster_id, "topic": c["topic"], "current_state": c["current_state"],
                         "decisions": decs, "edges": edges})


@app.get("/api/graph")
def graph(request: Request) -> JSONResponse:
    nodes = [decision_summary(d) for d in CONN.execute("SELECT * FROM decisions ORDER BY decided_at")]
    lanes = {c["cluster_id"]: c["topic"] for c in rows("SELECT cluster_id, topic FROM clusters")}
    for n in nodes:
        n["lane"] = lanes.get(n["cluster_id"])
    return out(request, {"nodes": nodes, "edges": rows("SELECT src, dst, kind, scope, aspect, rationale FROM decision_edges"),
                         "lanes": [{"cluster_id": k, "topic": v} for k, v in lanes.items()
                                   if any(n["cluster_id"] == k for n in nodes)]})


@app.get("/api/conflicts")
def list_conflicts(request: Request) -> JSONResponse:
    res = []
    for c in CONN.execute("SELECT * FROM conflicts ORDER BY conflict_id"):
        sides = []
        for s in CONN.execute("SELECT * FROM conflict_sides WHERE conflict_id=? ORDER BY side", (c["conflict_id"],)):
            sides.append({"side": s["side"], "claimant": s["claimant"], "claim": s["claim"],
                          "evidence": evidence_for("conflict_side", f"{c['conflict_id']}:{s['side']}")})
        dec = CONN.execute("SELECT decision_id FROM decisions WHERE cluster_id=? AND status='contested' LIMIT 1",
                           (c["cluster_id"],)).fetchone()
        res.append({"conflict_id": c["conflict_id"], "cluster_id": c["cluster_id"], "topic": c["topic"],
                    "summary": c["summary"], "decision_id": dec[0] if dec else None, "sides": sides,
                    "note": "Precedent will not choose a side; resolve this with the people involved."})
    return out(request, res)


@app.get("/api/emails/{message_id:path}")
def get_email(request: Request, message_id: str) -> JSONResponse:
    mid = message_id if message_id.startswith("<") else f"<{message_id}>"
    r = CONN.execute("SELECT * FROM emails WHERE message_id=?", (mid,)).fetchone()
    if r is None:
        raise HTTPException(404, "email not found")
    return out(request, {**email_card(mid), "new_text": r["new_text"], "quoted_text": r["quoted_text"],
                         "fwd_text": r["fwd_text"], "fwd_meta": _j(r["fwd_meta"], None),
                         "attachments": _j(r["attachment_names"], []),
                         "thread": [email_card(m) for (m,) in CONN.execute(
                             "SELECT message_id FROM emails WHERE thread_id=? ORDER BY sent_at", (r["thread_id"],))]})


@app.get("/api/eval/latest")
def eval_latest(request: Request) -> JSONResponse:
    if not EVAL_EXPORT.exists():
        raise HTTPException(404, "no evaluation exported yet (run python -m eval.run)")
    return out(request, json.loads(EVAL_EXPORT.read_text(encoding="utf-8")))


# ------------------------------------------------------------------ ask / feedback
class AskBody(BaseModel):
    question: str


@app.post("/api/ask")
async def api_ask(request: Request, body: AskBody) -> JSONResponse:
    q = body.question.strip()
    if not q:
        raise HTTPException(400, "empty question")
    try:
        res = await ask_question(CONN, LLM(CONN, run_id="ask"), embedder(), q)
    except LLMOffline:
        raise HTTPException(503, "Demo mode is offline: only the suggested questions are cached. "
                                 "Turn demo mode off to ask new questions.")
    return out(request, res)


class DisputeBody(BaseModel):
    kind: str = "dispute"
    note: str = ""


@app.post("/api/decisions/{decision_id}/dispute")
def dispute(decision_id: str, body: DisputeBody) -> dict:
    CONN.execute("INSERT INTO feedback(decision_id, kind, note, created_at) VALUES(?,?,?,?)",
                 (decision_id, body.kind, body.note[:2000], datetime.now(timezone.utc).isoformat()))
    CONN.commit()
    return {"ok": True}


# ------------------------------------------------------------------ ingest + SSE
def _emit(run_id: str, event: dict) -> None:
    run = RUNS[run_id]
    event = {"run_id": run_id, "ts": datetime.now(timezone.utc).isoformat(), **event}
    run["events"].append(event)
    for q in list(run["subscribers"]):
        q.put_nowait(event)


async def _run_all(run_id: str, paths: list[Path]) -> None:
    try:
        _emit(run_id, {"event": "stage_start", "stage": "parse"})
        for t in DERIVED_TABLES:
            CONN.execute(f"DELETE FROM {t}")
        CONN.execute("INSERT INTO passages_fts(passages_fts) VALUES('delete-all')")
        CONN.execute("INSERT INTO decisions_fts(decisions_fts) VALUES('delete-all')")
        llm = LLM(CONN, run_id=run_id)
        s0 = await run_stage0(CONN, paths, llm=llm, run_id=run_id)
        _emit(run_id, {"event": "stage_done", "stage": "parse", **s0})
        res = await run_pipeline(CONN, PIPELINE_STAGES, run_id=run_id, emit=lambda e: _emit(run_id, e))
        RUNS[run_id]["status"] = "done"
        _emit(run_id, {"event": "run_done", "summary": {"parse": s0, **{k: v for k, v in res.items() if k != "run_id"}}})
    except Exception as ex:  # surfaced to the UI's error state
        RUNS[run_id]["status"] = "error"
        _emit(run_id, {"event": "error", "message": str(ex)[:500]})


@app.post("/api/ingest")
async def ingest(files: list[UploadFile] = File(...)) -> dict:
    if STATE["demo_mode"]:
        raise HTTPException(409, "Turn demo mode off before ingesting a new mailbox.")
    if any(r["status"] == "running" for r in RUNS.values()):
        raise HTTPException(409, "A run is already in progress.")
    run_id = "run-" + uuid.uuid4().hex[:8]
    dest = UPLOADS / run_id
    dest.mkdir(parents=True, exist_ok=True)
    paths = []
    for f in files:
        name = Path(f.filename or "upload.eml").name
        if Path(name).suffix.lower() not in (".eml", ".mbox", ".zip"):
            continue
        p = dest / name
        with p.open("wb") as fh:
            shutil.copyfileobj(f.file, fh)
        paths.append(p)
    if not paths:
        raise HTTPException(400, "upload .eml files, an .mbox, or a .zip of .eml files")
    RUNS[run_id] = {"status": "running", "events": [], "subscribers": []}
    asyncio.create_task(_run_all(run_id, paths))
    return {"run_id": run_id, "files": len(paths)}


@app.post("/api/ingest/corpus")
async def ingest_corpus() -> dict:
    """'Load demo corpus' button: run the full pipeline live over corpus/emails."""
    if STATE["demo_mode"]:
        raise HTTPException(409, "Turn demo mode off before running the pipeline.")
    if any(r["status"] == "running" for r in RUNS.values()):
        raise HTTPException(409, "A run is already in progress.")
    run_id = "run-" + uuid.uuid4().hex[:8]
    RUNS[run_id] = {"status": "running", "events": [], "subscribers": []}
    asyncio.create_task(_run_all(run_id, [settings.corpus_dir]))
    return {"run_id": run_id}


@app.get("/api/runs/{run_id}/events")
async def run_events(run_id: str, request: Request) -> StreamingResponse:
    if run_id not in RUNS:
        raise HTTPException(404, "unknown run")
    run = RUNS[run_id]
    q: asyncio.Queue = asyncio.Queue()
    for e in run["events"]:  # replay for late subscribers
        q.put_nowait(e)
    run["subscribers"].append(q)

    async def stream():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    e = await asyncio.wait_for(q.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield f"event: {e['event']}\ndata: {json.dumps(e, ensure_ascii=False)}\n\n"
                if e["event"] in ("run_done", "error"):
                    break
        finally:
            run["subscribers"].remove(q)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.get("/api/runs/{run_id}")
def run_status(run_id: str) -> dict:
    if run_id not in RUNS:
        raise HTTPException(404, "unknown run")
    r = RUNS[run_id]
    return {"run_id": run_id, "status": r["status"], "events": r["events"][-50:]}


# ------------------------------------------------------------------ demo mode
class DemoBody(BaseModel):
    enabled: bool = True


@app.post("/api/demo/load")
def demo_load(body: DemoBody | None = None) -> dict:
    """Load the cached run (ledger + LLM cache) and go offline: the five screens and the suggested questions work
    without network access."""
    enabled = body.enabled if body else True
    if enabled:
        if not DEMO_DB.exists():
            raise HTTPException(404, "no demo snapshot yet (python -m backend.demo snapshot)")
        src = sqlite3.connect(DEMO_DB)
        src.backup(CONN)
        src.close()
    STATE["demo_mode"] = enabled
    llm_mod.RUNTIME["offline"] = enabled
    return {"demo_mode": enabled}


# ------------------------------------------------------------------ frontend
DIST = ROOT / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str) -> FileResponse:
        f = DIST / path
        return FileResponse(f if path and f.is_file() else DIST / "index.html")


def main() -> None:
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
