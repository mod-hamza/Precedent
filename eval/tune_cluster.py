"""Grid-search Stage 3 clustering parameters on the DEV split. Eval-side (reads eval_private/).

Truth: a record's label is the GT lifecycle chain (connected component of `links`) of the decision whose evidence
lives in the record's thread; records in threads without a GT decision are their own singleton. Reports pairwise
precision / recall / F1 of "same cluster".
"""
from __future__ import annotations

import asyncio
import csv
import itertools
import json
import sqlite3
from pathlib import Path

from backend.embed import Embedder
from backend.llm import LLM
from backend.pipeline import cluster as C

ROOT = Path(__file__).resolve().parent.parent
PRIV = ROOT / "eval_private"


def chain_labels(gt: dict) -> dict[str, str]:
    parent = {d["id"]: d["id"] for d in gt["decisions"]}

    def find(x):
        while parent[x] != x:
            x = parent[x]
        return x

    for d in gt["decisions"]:
        for l in d["links"]:
            parent[find(d["id"])] = find(l["to"])
    return {d: find(d) for d in parent}


def truth(conn, recs, split="dev"):
    gt = json.load(open(PRIV / "ground_truth.json", encoding="utf-8"))
    chain = chain_labels(gt)
    split_of = {d["id"]: d["split"] for d in gt["decisions"]}
    manifest = {r["message_id"]: r for r in csv.DictReader(open(PRIV / "manifest.csv", encoding="utf-8"))}
    tsplit, tdec = {}, {}
    for mid, tid in conn.execute("SELECT message_id, thread_id FROM emails"):
        row = manifest[mid]
        tsplit[tid] = row["split"]
        for did in filter(None, row["decision_ids"].split(";")):
            if did.startswith("D"):
                tdec[tid] = did
    keep, labels = [], []
    for i, r in enumerate(recs):
        if tsplit.get(r.thread_id) != split:
            continue
        did = tdec.get(r.thread_id)
        keep.append(i)
        labels.append(chain[did] if did and split_of[did] == split else f"solo:{r.record_id}")
    return keep, labels


def score(groups, keep, labels):
    owner = {i: g for g, m in enumerate(groups) for i in m}
    tp = fp = fn = 0
    for (a, la), (b, lb) in itertools.combinations(zip(keep, labels), 2):
        same_pred, same_true = owner[a] == owner[b], la == lb
        tp += same_pred and same_true
        fp += same_pred and not same_true
        fn += same_true and not same_pred
    p = tp / max(1, tp + fp)
    r = tp / max(1, tp + fn)
    return p, r, 2 * p * r / max(1e-9, p + r)


def main() -> None:
    conn = sqlite3.connect(ROOT / "data" / "precedent.db")
    conn.row_factory = sqlite3.Row
    emb = Embedder(conn)
    recs = C.load_records(conn)
    keep, labels = truth(conn, recs)
    print(f"dev records: {len(keep)}, true chains with >1 record: "
          f"{sum(1 for l in set(labels) if labels.count(l) > 1)}  embedder={emb.name}")
    rows = []
    for thr in (0.45, 0.5, 0.55, 0.6, 0.62, 0.65, 0.7, 0.75):
        for bonus in (0.0, 0.15, 0.25, 0.35):
            groups = C.cluster_records(recs, emb, threshold=thr, entity_bonus=bonus)
            rows.append((score(groups, keep, labels), thr, bonus, len(groups)))
    for (p, r, f), thr, bonus, n in sorted(rows, key=lambda x: -x[0][2])[:12]:
        print(f"thr={thr:.2f} bonus={bonus:.2f}  P={p:.2f} R={r:.2f} F1={f:.2f}  clusters={n}")
    groups = C.cluster_records(recs, emb)
    p, r, f = score(groups, keep, labels)
    print(f"current defaults thr={C.THRESHOLD} bonus={C.ENTITY_BONUS}: P={p:.2f} R={r:.2f} F1={f:.2f} clusters={len(groups)}")
    groups = asyncio.run(C.llm_groups(LLM(conn, run_id="tune"), recs))
    p, r, f = score(groups, keep, labels)
    print(f"llm mode: P={p:.2f} R={r:.2f} F1={f:.2f} clusters={len(groups)}")


if __name__ == "__main__":
    main()
