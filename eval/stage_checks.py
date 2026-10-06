"""Dev-split checks for Stages 1-2 (triage recall, where records land). Eval-side: may read eval_private/.

python -m eval.stage_checks [--split dev]

Only aggregate numbers and *dev* misses are printed; the holdout stays unexamined until the frozen run (PRD §11).
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRIV = ROOT / "eval_private"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev", choices=["dev", "holdout"])
    ap.add_argument("--db", default=str(ROOT / "data" / "precedent.db"))
    args = ap.parse_args()

    manifest = {r["message_id"]: r for r in csv.DictReader(open(PRIV / "manifest.csv", encoding="utf-8"))}
    gt = json.load(open(PRIV / "ground_truth.json", encoding="utf-8"))
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    thread_of = {r["message_id"]: r["thread_id"] for r in conn.execute("SELECT message_id, thread_id FROM emails")}
    kept = {r[0]: bool(r[1]) for r in conn.execute("SELECT thread_id, has_candidate FROM thread_triage")}

    # --- triage recall: every thread holding evidence for a GT decision of this split must pass
    miss = defaultdict(list)
    n_threads = 0
    for d in (x for x in gt["decisions"] if x["split"] == args.split):
        tids = {thread_of[e["message_id"]] for e in d["evidence_message_ids"] if e["message_id"] in thread_of}
        for t in tids:
            n_threads += 1
            if not kept.get(t, False):
                miss[d["id"]].append(t)
    n_miss = sum(len(v) for v in miss.values())
    print(f"[{args.split}] triage recall on GT decision threads: {n_threads - n_miss}/{n_threads} "
          f"({100 * (n_threads - n_miss) / max(1, n_threads):.1f}%)  target >= 98%")
    if args.split == "dev":
        for did, ts in sorted(miss.items()):
            print(f"   missed {did}: {ts}")

    # --- where do records land? bucket of each record's thread (decision / non_decision / filler)
    bucket_of_thread: dict[str, set] = defaultdict(set)
    for mid, row in manifest.items():
        if row["split"] == args.split and mid in thread_of:
            bucket_of_thread[thread_of[mid]].add(row["bucket"])
    split_threads = set(bucket_of_thread)
    total = sum(1 for t in kept if t in split_threads)
    passed = sum(1 for t, k in kept.items() if k and t in split_threads)
    print(f"[{args.split}] threads passing triage: {passed}/{total}")
    counts = defaultdict(lambda: defaultdict(int))
    for r in conn.execute("SELECT thread_id, stance FROM records"):
        if r["thread_id"] in split_threads:
            b = "decision" if "decision" in bucket_of_thread[r["thread_id"]] else \
                "non_decision" if "non_decision" in bucket_of_thread[r["thread_id"]] else "filler"
            counts[b][r["stance"]] += 1
    for b in ("decision", "non_decision", "filler"):
        print(f"   records in {b:12} threads: {dict(counts[b])}")
    q = conn.execute("SELECT COUNT(*), SUM(verified) FROM evidence WHERE owner_kind='record'").fetchone()
    print(f"[all] record evidence quotes verified: {q[1]}/{q[0]}")
    # PRD quote validity = 100%: every verified quote is a literal substring of its message's new or forwarded text
    bad = [r["id"] for r in conn.execute(
        "SELECT ev.id, ev.quote, e.new_text, e.fwd_text FROM evidence ev JOIN emails e USING(message_id) "
        "WHERE ev.verified=1") if not (r["quote"] in (r["new_text"] or "") or r["quote"] in (r["fwd_text"] or ""))]
    print(f"[all] verified quotes that are NOT verbatim substrings: {len(bad)}  (must be 0) {bad[:5]}")


if __name__ == "__main__":
    main()
