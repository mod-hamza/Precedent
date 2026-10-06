"""Stage 3: cluster extraction records into topic clusters (PRD §7 Stage 3).

Two modes (PRECEDENT_CLUSTER):
- "llm" (default): REASON groups all records in one call (records are short; ~100 fit easily). On dev this recovers
  lifecycle chains whose steps share neither wording nor a named entity ("raise to 59" -> "existing stay at 49").
- "embed": the embedding + rules method below, kept as the offline fallback.

Embedding mode: similarity = cosine(embed(topic_label + decision_text)) + ENTITY_BONUS * [records share a named entity]
Named entities (vendors, products, places: "Ledgerly", "Corvid", "v3") are the strongest same-topic signal in a
decision chain, and the small local embedder underrates them.

Average-linkage agglomerative clustering, merging only above THRESHOLD and only between clusters that share a
participant or have a very close pair (cosine >= STRONG). Then clusters are joined when a record's overrides_hint
points at a record in another cluster. Singletons are valid; nothing is forced together to hit a count.
Thresholds were tuned on the dev split (eval/tune_cluster.py) for this embedder.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from pathlib import Path
from dataclasses import dataclass, field

import numpy as np

from ..embed import Embedder
from ..llm import LLM
from ..models import ClusterResult

THRESHOLD = 0.62
ENTITY_BONUS = 0.25
STRONG = 0.85
OVERRIDE_SIM = 0.55

_STOP = {
    "a", "an", "the", "and", "or", "to", "of", "for", "in", "on", "at", "by", "with", "from", "we", "our", "all",
    "approve", "approved", "launch", "keep", "use", "move", "stay", "switch", "set", "start", "adopt", "hire",
    "offer", "cut", "add", "drop", "contract", "defer", "delay", "proceed", "grant", "give", "go", "make", "run",
    "eur", "q1", "q2", "q3", "q4", "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december", "monday", "tuesday", "wednesday", "thursday", "friday",
    "saturday", "sunday", "new", "existing", "pro", "plan", "team", "customer", "customers",
}


def entities(text: str, people_tokens: set[str]) -> set[str]:
    """Capitalised or alphanumeric product-like tokens (Ledgerly, NimbusHost, v3, SLA), minus people and stopwords."""
    toks = re.findall(r"\b(?:[A-Z][\w&-]+|[a-z]+\d[\w.]*|[A-Z]{2,})\b", text)
    out = set()
    for t in toks:
        low = t.casefold().strip("-")
        if len(low) < 2 or low in _STOP or low in people_tokens:
            continue
        out.add(low)
    return out


@dataclass
class Rec:
    record_id: str
    thread_id: str
    topic_label: str
    decision_text: str
    stance: str
    decision_date: str
    overrides_hint: str | None
    participants: set[str]
    ents: set[str] = field(default_factory=set)

    @property
    def text(self) -> str:
        return f"{self.topic_label}: {self.decision_text}"


def load_records(conn: sqlite3.Connection) -> list[Rec]:
    people_tokens = set()
    for (name,) in conn.execute("SELECT canonical_name FROM people"):
        people_tokens |= {t.casefold() for t in name.split()}
    parts = {r[0]: set(json.loads(r[1])) for r in conn.execute("SELECT thread_id, participants FROM threads")}
    recs = []
    for r in conn.execute("SELECT * FROM records ORDER BY decision_date, record_id"):
        rec = Rec(r["record_id"], r["thread_id"], r["topic_label"] or "", r["decision_text"] or "", r["stance"],
                  r["decision_date"], r["overrides_hint"], parts.get(r["thread_id"], set()))
        rec.ents = entities(f"{rec.topic_label} {rec.decision_text} {rec.overrides_hint or ''}", people_tokens)
        recs.append(rec)
    return recs


def similarity(recs: list[Rec], emb: np.ndarray, entity_bonus: float = ENTITY_BONUS) -> tuple[np.ndarray, np.ndarray]:
    cos = emb @ emb.T
    n = len(recs)
    shared = np.zeros((n, n), dtype=bool)
    for i in range(n):
        for j in range(i + 1, n):
            if recs[i].ents & recs[j].ents:
                shared[i, j] = shared[j, i] = True
    return cos + entity_bonus * shared, cos


def agglomerate(sim: np.ndarray, link_ok: np.ndarray, threshold: float) -> list[list[int]]:
    """Average linkage with a can-link mask (Lance-Williams update)."""
    n = sim.shape[0]
    S = sim.astype(np.float64).copy()
    ok = link_ok.copy()
    np.fill_diagonal(S, -np.inf)
    size = np.ones(n)
    members = {i: [i] for i in range(n)}
    alive = np.ones(n, dtype=bool)
    while True:
        cand = np.where(ok & alive[:, None] & alive[None, :], S, -np.inf)
        np.fill_diagonal(cand, -np.inf)
        k = int(np.argmax(cand))
        i, j = divmod(k, n)
        if cand[i, j] < threshold:
            break
        S[i] = (size[i] * S[i] + size[j] * S[j]) / (size[i] + size[j])
        S[:, i] = S[i]
        S[i, i] = -np.inf
        ok[i] = ok[i] | ok[j]
        ok[:, i] = ok[i]
        size[i] += size[j]
        members[i] += members.pop(j)
        alive[j] = False
    return [sorted(m) for m in members.values()]


def cluster_records(recs: list[Rec], embedder: Embedder, threshold: float = THRESHOLD,
                    entity_bonus: float = ENTITY_BONUS, override_sim: float = OVERRIDE_SIM) -> list[list[int]]:
    if not recs:
        return []
    emb = embedder.embed([r.text for r in recs])
    sim, cos = similarity(recs, emb, entity_bonus)
    n = len(recs)
    share = np.array([[bool(recs[i].participants & recs[j].participants) for j in range(n)] for i in range(n)])
    groups = agglomerate(sim, share | (cos >= STRONG), threshold)

    # overrides_hint: "changes the earlier plan to X" pulls in the cluster holding X
    owner = {i: g for g, members in enumerate(groups) for i in members}
    hinted = [i for i, r in enumerate(recs) if r.overrides_hint]
    if hinted:
        hemb = embedder.embed([recs[i].overrides_hint for i in hinted])
        parent = list(range(len(groups)))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        hs = hemb @ emb.T
        for row, i in enumerate(hinted):
            for j in np.argsort(-hs[row])[:3]:
                j = int(j)
                if j != i and recs[j].decision_date <= recs[i].decision_date and hs[row, j] >= override_sim \
                        and recs[i].ents & recs[j].ents:
                    parent[find(owner[i])] = find(owner[j])
        merged: dict[int, list[int]] = {}
        for g, members in enumerate(groups):
            merged.setdefault(find(g), []).extend(members)
        groups = [sorted(m) for m in merged.values()]
    return sorted(groups, key=lambda g: min(recs[i].decision_date for i in g))


CLUSTER_PROMPT = (Path(__file__).resolve().parent.parent / "prompts" / "cluster.md").read_text(encoding="utf-8")


async def llm_groups(llm: LLM, recs: list[Rec]) -> list[list[int]]:
    alias = {f"r{i + 1}": i for i in range(len(recs))}
    lines = [f"{a} | {recs[i].decision_date} | {recs[i].stance} | {recs[i].topic_label} | {recs[i].decision_text}"
             + (f" | overrides: {recs[i].overrides_hint}" if recs[i].overrides_hint else "")
             for a, i in alias.items()]
    user = "RECORDS (id | date | stance | topic | decision | overrides hint)\n" + "\n".join(lines)
    res = await llm.structured("REASON", CLUSTER_PROMPT, user, ClusterResult, stage="cluster")
    seen: set[int] = set()
    groups = []
    for g in res.groups:
        members = [alias[r.strip()] for r in g.record_ids if r.strip() in alias and alias[r.strip()] not in seen]
        seen.update(members)
        if members:
            groups.append(sorted(members))
    groups += [[i] for i in range(len(recs)) if i not in seen]  # anything the model dropped stays a singleton
    return sorted(groups, key=lambda g: min(recs[i].decision_date for i in g))


async def run_cluster(conn: sqlite3.Connection, llm: LLM | None = None, embedder: Embedder | None = None,
                      mode: str | None = None) -> dict:
    mode = mode or os.environ.get("PRECEDENT_CLUSTER", "llm")
    recs = load_records(conn)
    if mode == "llm" and llm is not None:
        groups = await llm_groups(llm, recs)
        method = "llm"
    else:
        embedder = embedder or Embedder(conn)
        groups = cluster_records(recs, embedder)
        method = "embed:" + embedder.name
    conn.execute("UPDATE records SET cluster_id=NULL")
    conn.execute("DELETE FROM clusters")
    for members in groups:
        ids = sorted(recs[i].record_id for i in members)
        cid = "C-" + hashlib.sha1("|".join(ids).encode()).hexdigest()[:8]
        topic = max((recs[i].topic_label for i in members), key=lambda t: sum(recs[k].topic_label == t for k in members))
        conn.execute("INSERT INTO clusters(cluster_id, topic, summary, current_state, n_records) VALUES(?,?,?,?,?)",
                     (cid, topic, None, None, len(members)))
        for i in members:
            conn.execute("UPDATE records SET cluster_id=? WHERE record_id=?", (cid, recs[i].record_id))
    conn.commit()
    sizes = [len(g) for g in groups]
    return {"records": len(recs), "clusters": len(groups), "singletons": sizes.count(1),
            "largest": max(sizes, default=0), "method": method}
