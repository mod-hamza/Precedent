"""Evaluation harness (PRD §11). Reads eval_private/ and the pipeline's SQLite output; never imported by backend/.

python -m eval.run --split dev            # tuning loop
python -m eval.run --split holdout        # the ONE frozen holdout run (tag the commit first)
python -m eval.run --split both --no-qa   # skip the 30-question Q&A pass

Writes eval/results/eval_results.json (served read-only at /api/eval/latest) and eval/results/scorecard.md.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sqlite3
import statistics
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from backend.db import connect
from backend.embed import Embedder
from backend.llm import LLM
from backend.pipeline.ask import ask

from .judge import asserts_decided, genuine, grade_answer, supports
from .match import match_decisions
from .report import markdown

ROOT = Path(__file__).resolve().parent.parent
PRIV = ROOT / "eval_private"
OUT = ROOT / "eval" / "results"
STATUS = {"ACTIVE": "active", "AMENDED": "amended", "SUPERSEDED": "superseded", "CONTESTED": "contested"}
TARGETS = {"decision_recall": 0.85, "decision_precision": 0.85, "near_decision_fp_max": 2, "supersession_accuracy": 0.80,
           "conflicts_min": 2, "quote_validity": 1.0, "evidence_support": 0.90, "qa_accuracy": 0.85,
           "no_decision_correct": 5, "latency_p50_ms": 8000, "pipeline_minutes": 25}


def load_gt():
    gt = json.load(open(PRIV / "ground_truth.json", encoding="utf-8"))
    manifest = {r["message_id"]: r for r in csv.DictReader(open(PRIV / "manifest.csv", encoding="utf-8"))}
    return gt, manifest


def _git() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def predicted(conn: sqlite3.Connection, manifest: dict, split: str) -> list[dict]:
    ev = defaultdict(set)
    for r in conn.execute("SELECT owner_id, message_id FROM evidence WHERE owner_kind='decision' AND verified=1"):
        ev[r["owner_id"]].add(r["message_id"])
    out = []
    for d in conn.execute("SELECT * FROM decisions"):
        splits = [manifest[m]["split"] for m in ev[d["decision_id"]] if m in manifest]
        if splits and max(set(splits), key=splits.count) == split:
            out.append({"decision_id": d["decision_id"], "text": d["canonical_text"], "date": d["decided_at"],
                        "status": d["status"], "evidence": ev[d["decision_id"]]})
    return out


async def eval_split(conn, llm, emb, gt, manifest, split: str, run_qa: bool) -> dict:
    gtd = [d for d in gt["decisions"] if d["split"] == split]
    gts = [{"id": d["id"], "text": d["canonical_text"], "date": d["date"],
            "evidence": {e["message_id"] for e in d["evidence_message_ids"]}} for d in gtd]
    by_gt = {d["id"]: d for d in gtd}
    preds = predicted(conn, manifest, split)
    pred_by = {p["decision_id"]: p for p in preds}
    m = await match_decisions(llm, emb, preds, gts)
    match = {g: (p, v) for g, p, v in m["pairs"]}
    weight = {"yes": 1.0, "partial": 0.5}
    hit = sum(weight[v] for _, v in match.values())
    res: dict = {"split": split, "n_gt": len(gts), "n_pred": len(preds), "judged_pairs": m["judged"]}
    res["decision_recall"] = round(hit / max(1, len(gts)), 3)
    res["decision_precision"] = round(hit / max(1, len(preds)), 3)
    res["partial_matches"] = sum(v == "partial" for _, v in match.values())

    # status accuracy among matched
    st_ok = sum(pred_by[p]["status"] == STATUS[by_gt[g]["status"]] for g, (p, _) in match.items())
    res["status_accuracy"] = round(st_ok / max(1, len(match)), 3)

    # supersession / amendment edges (src is the later decision)
    gt_edges = set()
    for d in gtd:
        for l in d["links"]:
            if l["to"] in by_gt:
                o = by_gt[l["to"]]
                a, b = (d["id"], o["id"]) if d["date"] >= o["date"] else (o["id"], d["id"])
                gt_edges.add((a, b, l["kind"]))
    pe = {(r["src"], r["dst"]): r["kind"] for r in conn.execute("SELECT src, dst, kind FROM decision_edges")}
    e_hit = e_kind = 0
    edge_rows = []
    for a, b, kind in sorted(gt_edges):
        pa, pb = match.get(a, (None,))[0], match.get(b, (None,))[0]
        ok = bool(pa and pb and (pa, pb) in pe)
        e_hit += ok
        e_kind += ok and pe[(pa, pb)] == kind
        edge_rows.append({"src": a, "dst": b, "kind": kind, "recovered": ok, "kind_ok": ok and pe[(pa, pb)] == kind})
    res["supersession_accuracy"] = round(e_hit / max(1, len(gt_edges)), 3)
    res["supersession_kind_accuracy"] = round(e_kind / max(1, len(gt_edges)), 3)
    res["edges"] = edge_rows

    # conflicts
    sides = defaultdict(lambda: defaultdict(set))
    for r in conn.execute("SELECT owner_id, message_id FROM evidence WHERE owner_kind='conflict_side'"):
        cid, side = r["owner_id"].split(":")
        sides[cid][side].add(r["message_id"])
    conf_rows = []
    for d in gtd:
        if d["status"] != "CONTESTED":
            continue
        gev = {e["message_id"] for e in d["evidence_message_ids"]}
        surfaced = [cid for cid, s in sides.items() if sum(bool(ms & gev) for ms in s.values()) >= 2]
        contested = d["id"] in match and pred_by[match[d["id"]][0]]["status"] == "contested"
        conf_rows.append({"gt": d["id"], "surfaced": bool(surfaced), "contested_status": contested,
                          "detected": bool(surfaced) and contested})
    res["conflicts"] = conf_rows
    res["conflicts_detected"] = sum(c["detected"] for c in conf_rows)

    # near-decision false positives: a predicted decision citing an N-item's emails that claims it was decided
    near = []
    for n in (x for x in gt["non_decisions"] if x["split"] == split):
        nev = {e["message_id"] for e in n["evidence_message_ids"]}
        cands = [p for p in preds if p["evidence"] & nev]
        verdicts = await asyncio.gather(*(asserts_decided(llm, n["topic"], n["outcome"], p["text"]) for p in cands))
        fp = [p["decision_id"] for p, v in zip(cands, verdicts) if v.asserts_decided]
        near.append({"id": n["id"], "topic": n["topic"], "trap": n["trap_type"], "false_positive": bool(fp), "decisions": fp})
    res["near_decisions"] = near
    res["near_decision_fp"] = sum(x["false_positive"] for x in near)
    res["near_decision_n"] = len(near)

    # evidence support: strict = cited emails within the GT evidence set; judged = strict or LLM says it supports
    strict = judged = total = 0
    for g, (p, _) in match.items():
        gev = {e["message_id"] for e in by_gt[g]["evidence_message_ids"]}
        for e in conn.execute("SELECT message_id, quote FROM evidence WHERE owner_kind='decision' AND owner_id=? "
                              "AND verified=1", (p,)):
            total += 1
            if e["message_id"] in gev:
                strict += 1
                judged += 1
            elif (await supports(llm, pred_by[p]["text"], e["quote"])).supports:
                judged += 1
    res["evidence_support_strict"] = round(strict / max(1, total), 3)
    res["evidence_support"] = round(judged / max(1, total), 3)

    res["decisions_table"] = [
        {"gt_id": d["id"], "gt_text": d["canonical_text"], "gt_date": d["date"], "gt_status": STATUS[d["status"]],
         "result": {"yes": "hit", "partial": "partial"}[match[d["id"]][1]] if d["id"] in match else "miss",
         "pred_id": match[d["id"]][0] if d["id"] in match else None,
         "pred_text": pred_by[match[d["id"]][0]]["text"] if d["id"] in match else None,
         "pred_date": pred_by[match[d["id"]][0]]["date"] if d["id"] in match else None,
         "pred_status": pred_by[match[d["id"]][0]]["status"] if d["id"] in match else None}
        for d in gtd]
    unmatched = [p for p in preds if p["decision_id"] not in {x for x, _ in match.values()}]
    verdicts = await asyncio.gather(*(genuine(llm, p["text"]) for p in unmatched))
    res["unmatched_predictions"] = [{"pred_id": p["decision_id"], "text": p["text"], "date": p["date"],
                                     "judged_genuine_decision": v.genuine_decision, "reason": v.reason}
                                    for p, v in zip(unmatched, verdicts)]
    # Context for precision: the GT lists 40 planted decisions, so genuine decisions it does not list count against
    # strict precision. Reported separately; the strict number stays the headline.
    res["unmatched_genuine"] = sum(v.genuine_decision for v in verdicts)

    # triage recall
    thread_of = {r[0]: r[1] for r in conn.execute("SELECT message_id, thread_id FROM emails")}
    kept = {r[0]: bool(r[1]) for r in conn.execute("SELECT thread_id, has_candidate FROM thread_triage")}
    tids = {thread_of[e["message_id"]] for d in gtd for e in d["evidence_message_ids"] if e["message_id"] in thread_of}
    res["triage_recall"] = round(sum(kept.get(t, False) for t in tids) / max(1, len(tids)), 3)

    if run_qa:
        res.update(await eval_qa(conn, llm, emb, gt, split))
    return res


async def eval_qa(conn, llm, emb, gt, split: str) -> dict:
    split_of = {d["id"]: d["split"] for d in gt["decisions"]} | {n["id"]: n["split"] for n in gt["non_decisions"]}
    status_of = {d["id"]: d["status"] for d in gt["decisions"]}
    gold_msgs = {d["id"]: {e["message_id"] for e in d["evidence_message_ids"]} for d in gt["decisions"] + gt["non_decisions"]}
    rows = []
    for q in gt["qa"]:
        refs = q["evidence_decisions"]
        if not refs or split_of.get(refs[0]) != split:
            continue
        expected = "no_decision" if any(r.startswith("N") for r in refs) else \
            "contested" if any(status_of.get(r) == "CONTESTED" for r in refs) else "found"
        a = await ask(conn, LLM(conn, run_id=f"eval-qa-{split}"), emb, q["question"])
        cited = {c["message_id"] for c in a["citations"]} | {c["message_id"] for c in a["closest"]}
        gold = set().union(*(gold_msgs.get(r, set()) for r in refs))
        ledger = [f"{d['decided_at']} [{d['status']}] {d['canonical_text']}" for d in a["decisions"]]
        j = await grade_answer(llm, q["question"], q["expected"], a["answer_md"], [c["quote"] for c in a["citations"]],
                               ledger)
        status_ok = a["status"] == expected or (expected == "found" and a["status"] == "partial" and j.facts_present)
        gold_cited = bool(cited & gold)
        full = j.facts_present and status_ok and gold_cited and not j.unsupported_claims
        score = 1.0 if full else 0.5 if (j.facts_present and status_ok) else 0.0
        rows.append({"id": q["id"], "question": q["question"], "expected": q["expected"], "expected_status": expected,
                     "status": a["status"], "answer_md": a["answer_md"], "confidence": a["confidence"],
                     "facts_present": j.facts_present, "status_ok": status_ok, "gold_cited": gold_cited,
                     "unsupported_claims": j.unsupported_claims, "judge_reason": j.reason, "score": score,
                     "latency_ms": a["latency_ms"]})
    lat = [r["latency_ms"] for r in rows]
    nd = [r for r in rows if r["expected_status"] == "no_decision"]
    return {"qa": rows, "qa_accuracy": round(sum(r["score"] for r in rows) / max(1, len(rows)), 3),
            "qa_n": len(rows), "no_decision_correct": sum(r["status"] == "no_decision" for r in nd),
            "no_decision_n": len(nd), "latency_p50_ms": int(statistics.median(lat)) if lat else None,
            "latency_p90_ms": int(sorted(lat)[int(0.9 * (len(lat) - 1))]) if lat else None}


def global_metrics(conn) -> dict:
    bad = total = 0
    for r in conn.execute("SELECT ev.quote, e.new_text, e.fwd_text FROM evidence ev JOIN emails e USING(message_id) "
                          "WHERE ev.verified=1 AND ev.owner_kind IN ('decision','conflict_side','record')"):
        total += 1
        bad += not (r["quote"] in (r["new_text"] or "") or r["quote"] in (r["fwd_text"] or ""))
    secs = {}
    for r in conn.execute("SELECT stage, notes FROM runs ORDER BY finished_at"):
        secs[r["stage"]] = json.loads(r["notes"] or "{}").get("seconds")
    return {"quote_validity": round(1 - bad / max(1, total), 4), "quotes_checked": total,
            "pipeline_seconds_by_stage": secs,
            "pipeline_minutes": round(sum(v for k, v in secs.items() if v and k != "parse") / 60, 1)}


async def main_async(args) -> None:
    gt, manifest = load_gt()
    conn = connect()
    llm = LLM(conn, run_id="eval")
    emb = Embedder(conn)
    splits = ["dev", "holdout"] if args.split == "both" else [args.split]
    prev = json.loads((OUT / "eval_results.json").read_text(encoding="utf-8")) if (OUT / "eval_results.json").exists() else {}
    results = prev.get("splits", {})
    for s in splits:
        results[s] = await eval_split(conn, llm, emb, gt, manifest, s, not args.no_qa)
        results[s]["evaluated_at"] = datetime.now(timezone.utc).isoformat()
        results[s]["git_commit"] = _git()
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "git_commit": _git(),
               "banner": "Synthetic corpus; ground truth hidden from the pipeline.", "targets": TARGETS,
               "global": global_metrics(conn), "splits": results,
               "models": {r: __import__("backend.config", fromlist=["settings"]).settings.role(r).model
                          for r in ("FAST", "CORE", "REASON", "ANSWER", "JUDGE")}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "eval_results.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    md = markdown(payload)
    (OUT / "scorecard.md").write_text(md, encoding="utf-8")
    print(md)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev", choices=["dev", "holdout", "both"])
    ap.add_argument("--no-qa", action="store_true")
    asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    main()
