"""Decision matching (PRD §11): candidate pairs by date (|diff| <= 5 days) and either embedding cosine >= 0.55 or a
shared evidence email; each candidate judged yes/partial/no by the JUDGE model; one-to-one assignment by maximum
weight (Hungarian). yes = 1, partial = 0.5."""
from __future__ import annotations

import asyncio
from datetime import date

import numpy as np
from scipy.optimize import linear_sum_assignment

from backend.embed import Embedder
from backend.llm import LLM

from .judge import same_decision

DATE_WINDOW, COS_MIN = 5, 0.55
WEIGHT = {"yes": 1.0, "partial": 0.5, "no": 0.0}


async def match_decisions(llm: LLM, emb: Embedder, preds: list[dict], gts: list[dict]) -> dict:
    """preds: {decision_id, text, date, evidence:set}; gts: {id, text, date, evidence:set}.
    Returns {"pairs": [(gt_id, pred_id, verdict)], "judged": n}."""
    if not preds or not gts:
        return {"pairs": [], "judged": 0}
    pv = emb.embed([p["text"] for p in preds])
    gv = emb.embed([g["text"] for g in gts])
    cos = gv @ pv.T
    cands = []
    for i, g in enumerate(gts):
        for j, p in enumerate(preds):
            if abs((date.fromisoformat(p["date"]) - date.fromisoformat(g["date"])).days) > DATE_WINDOW:
                continue
            if cos[i, j] >= COS_MIN or (g["evidence"] & p["evidence"]):
                cands.append((i, j))
    verdicts = await asyncio.gather(*(same_decision(llm, preds[j]["text"], preds[j]["date"], gts[i]["text"], gts[i]["date"])
                                      for i, j in cands))
    W = np.zeros((len(gts), len(preds)))
    V = {}
    for (i, j), v in zip(cands, verdicts):
        W[i, j] = WEIGHT[v.verdict]
        V[(i, j)] = v.verdict
    rows, cols = linear_sum_assignment(-W)
    pairs = [(gts[i]["id"], preds[j]["decision_id"], V[(i, j)]) for i, j in zip(rows, cols) if W[i, j] > 0]
    return {"pairs": pairs, "judged": len(cands)}
