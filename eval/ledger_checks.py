"""Approximate dev-split checks for Stage 4 output (eval side; reads eval_private/).

Matching here is cheap and approximate: a predicted decision matches a GT decision when it cites at least one of that
decision's evidence emails and the dates are within 5 days (best evidence overlap wins). The PRD's LLM-judged,
Hungarian-matched scorer lives in the eval harness; this is the fast loop used while tuning.

python -m eval.ledger_checks [--split dev]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRIV = ROOT / "eval_private"
STATUS = {"ACTIVE": "active", "AMENDED": "amended", "SUPERSEDED": "superseded", "CONTESTED": "contested"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev", choices=["dev", "holdout"])
    args = ap.parse_args()
    verbose = args.split == "dev"
    gt = json.load(open(PRIV / "ground_truth.json", encoding="utf-8"))
    gtd = {d["id"]: d for d in gt["decisions"] if d["split"] == args.split}
    conn = sqlite3.connect(ROOT / "data" / "precedent.db")
    conn.row_factory = sqlite3.Row
    preds = {r["decision_id"]: dict(r) for r in conn.execute("SELECT * FROM decisions")}
    pev = defaultdict(set)
    for r in conn.execute("SELECT owner_id, message_id FROM evidence WHERE owner_kind='decision'"):
        pev[r["owner_id"]].add(r["message_id"])
    gev = {k: {e["message_id"] for e in d["evidence_message_ids"]} for k, d in gtd.items()}
    split_msgs = set().union(*gev.values()) if gev else set()

    match: dict[str, str] = {}  # gt id -> pred id
    for gid, d in gtd.items():
        best = None
        for pid, p in preds.items():
            ov = len(pev[pid] & gev[gid])
            if ov and abs((date.fromisoformat(p["decided_at"]) - date.fromisoformat(d["date"])).days) <= 5:
                if best is None or ov > best[0]:
                    best = (ov, pid)
        if best:
            match[gid] = best[1]

    n = len(gtd)
    print(f"[{args.split}] GT decisions matched: {len(match)}/{n}")
    st_ok = sum(preds[p]["status"] == STATUS[gtd[g]["status"]] for g, p in match.items())
    print(f"[{args.split}] status correct among matched: {st_ok}/{len(match)}")
    if verbose:
        for g in sorted(gtd):
            p = match.get(g)
            got = f"{p} {preds[p]['status']:10} {preds[p]['canonical_text'][:70]}" if p else "MISS"
            flag = "" if p and preds[p]["status"] == STATUS[gtd[g]["status"]] else "   <--"
            print(f"   {g} {STATUS[gtd[g]['status']]:10} -> {got}{flag}")

    # edges: GT links listed on both ends; src is the later decision
    gt_edges = set()
    for g, d in gtd.items():
        for l in d["links"]:
            if l["to"] in gtd:
                a, b = (g, l["to"]) if d["date"] >= gtd[l["to"]]["date"] else (l["to"], g)
                gt_edges.add((a, b, l["kind"]))
    pe = {(r["src"], r["dst"]): r["kind"] for r in conn.execute("SELECT * FROM decision_edges")}
    found = kind_ok = 0
    for a, b, kind in sorted(gt_edges):
        pa, pb = match.get(a), match.get(b)
        hit = pa and pb and (pa, pb) in pe
        found += bool(hit)
        kind_ok += bool(hit and pe[(pa, pb)] == kind)
        if verbose and not hit:
            print(f"   edge missed: {a} -{kind}-> {b}  (pred {pa} -> {pb})")
    print(f"[{args.split}] supersession edges recovered (direction): {found}/{len(gt_edges)}, kind also right: {kind_ok}")

    # conflicts: GT contested decision surfaced as a conflict with >= 2 sides citing its evidence
    sides = defaultdict(list)
    for r in conn.execute("SELECT owner_id, message_id FROM evidence WHERE owner_kind='conflict_side'"):
        cid, side = r["owner_id"].split(":")
        sides[cid].append((side, r["message_id"]))
    for g, d in gtd.items():
        if d["status"] != "CONTESTED":
            continue
        ok = [cid for cid, s in sides.items() if len({side for side, m in s if m in gev[g]}) >= 2]
        print(f"[{args.split}] conflict {g}: {'surfaced as ' + ', '.join(ok) if ok else 'NOT surfaced'}"
              f"; matched decision status = {preds[match[g]]['status'] if g in match else '-'}")

    # precision proxy: predicted decisions citing this split's emails that match no GT decision
    matched_p = set(match.values())
    extra = [p for p in preds if p not in matched_p and pev[p] & split_msgs]
    other = [p for p in preds if not pev[p] & split_msgs]
    print(f"[{args.split}] predicted decisions on GT-decision emails but unmatched: {len(extra)}; "
          f"on other emails (filler / near-decision / other split): {len(other)}")
    if verbose:
        for p in extra:
            print(f"   extra {p} {preds[p]['decided_at']} {preds[p]['status']:10} {preds[p]['canonical_text'][:90]}")


if __name__ == "__main__":
    main()
