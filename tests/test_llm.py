import asyncio
import json

import numpy as np

from backend import llm as llm_mod
from backend.db import connect
from backend.embed import Embedder
from backend.models import Answer, ExtractionResult, ReconcileResult


def _walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def test_strict_schema_is_closed_and_fully_required():
    for model in (ExtractionResult, ReconcileResult, Answer):
        s = llm_mod.strict_schema(model)
        for node in _walk(s):
            if "properties" in node:
                assert node["additionalProperties"] is False
                assert set(node["required"]) == set(node["properties"])
            assert not (llm_mod._UNSUPPORTED_KEYS - {"title", "default"}) & node.keys()


def test_cache_repair_and_cost(tmp_path, monkeypatch):
    conn = connect(tmp_path / "t.db")
    llm = llm_mod.LLM(conn, run_id="t")
    calls = []
    good = {"records": []}

    async def fake_call(cfg, system, user, schema):
        calls.append(user)
        text = '{"records": "not-a-list"}' if len(calls) == 1 else json.dumps(good)  # first answer is invalid
        return text, 1000, 100, llm_mod._cost(cfg.model, 1000, 100)

    monkeypatch.setattr(llm, "_call", fake_call)
    out = asyncio.run(llm.structured("CORE", "sys", "thread text", ExtractionResult, stage="extract"))
    assert out.records == [] and len(calls) == 2 and "failed schema validation" in calls[1]
    out2 = asyncio.run(llm.structured("CORE", "sys", "thread text", ExtractionResult, stage="extract"))
    assert out2 == out and len(calls) == 2  # served from cache
    rows = llm_mod.usage_by_stage(conn, "t")
    assert rows == [{"stage": "extract", "calls": 2, "cached": 1, "tokens_in": 2000, "tokens_out": 200,
                     "cost_usd": round(2 * llm_mod._cost(llm_mod.settings.role("CORE").model, 1000, 100), 4)}]


def test_offline_mode_refuses_cache_miss(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_mod.settings.__class__, "offline", property(lambda self: True), raising=False)
    llm = llm_mod.LLM(connect(tmp_path / "t.db"))
    try:
        asyncio.run(llm.structured("FAST", "s", "u", ExtractionResult, stage="x"))
        raise AssertionError("expected LLMOffline")
    except llm_mod.LLMOffline:
        pass


def test_hash_embedder_is_deterministic_and_normalised(tmp_path):
    e = Embedder(connect(tmp_path / "t.db"), backend="hash")
    a = e.embed(["switch payment provider to Ledgerly", "switch payment provider to Ledgerly", "lunch order friday"])
    assert np.allclose(np.linalg.norm(a, axis=1), 1)
    assert a[0] @ a[1] > 0.999 and a[0] @ a[2] < 0.5
