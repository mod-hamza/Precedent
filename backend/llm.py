"""Single entry point for every model call (PRD §5).

- Roles FAST / CORE / REASON map to models via config. Two providers: "openai" (any OpenAI-compatible endpoint; the
  hackathon's Alibaba Cloud Model Studio) and "anthropic".
- Output is constrained to a JSON schema (response_format json_schema, or json_object plus the schema in the prompt
  where a model rejects json_schema) and validated by Pydantic; one repair retry on validation failure.
- Every call is cached on sha256(model + prompt + schema + effort); re-runs are free and demos reproducible.
- Token usage and cost are logged per stage in llm_calls.

Note: Claude 5.x models reject `temperature`; temperature 0 is sent everywhere else. Determinism beyond that comes
from the cache.
"""
from __future__ import annotations

import asyncio
import copy
import json
import os
import re
import sqlite3
import time
from typing import Any, TypeVar

import anthropic
import httpx
from pydantic import BaseModel, ValidationError

from .cache import LLMCache, cache_key
from .config import price, settings

T = TypeVar("T", bound=BaseModel)

_UNSUPPORTED_KEYS = {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf", "minLength",
                     "maxLength", "pattern", "minItems", "maxItems", "default", "title"}


RUNTIME = {"offline": False}  # flipped by the API in demo mode; settings.offline is the env default


class LLMError(RuntimeError):
    pass


class LLMRefusal(LLMError):
    pass


class LLMOffline(LLMError):
    pass


def strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Pydantic JSON schema -> structured-outputs-compatible schema (closed objects, all keys required)."""
    schema = copy.deepcopy(model.model_json_schema())

    def fix(node: Any) -> None:
        if isinstance(node, dict):
            # property *names* never reach here as keys: 'properties' children are recursed into below
            for k in _UNSUPPORTED_KEYS & node.keys():
                node.pop(k)
            if node.get("type") == "object" or "properties" in node:
                node["additionalProperties"] = False
                if "properties" in node:
                    node["required"] = list(node["properties"].keys())
            for key, v in node.items():
                if key == "properties" and isinstance(v, dict):
                    for prop in v.values():
                        fix(prop)
                else:
                    fix(v)
        elif isinstance(node, list):
            for v in node:
                fix(v)

    fix(schema)
    return schema


def _is_5x(model: str) -> bool:
    return any(model.startswith(p) for p in ("claude-opus-5", "claude-sonnet-5", "claude-fable-5"))


def _cost(model: str, tokens_in: int, tokens_out: int, cache_read: int = 0) -> float:
    pin, pout = price(model)
    return (tokens_in * pin + cache_read * pin * 0.1 + tokens_out * pout) / 1_000_000


_JSON_OBJECT_ONLY: set[str] = set()  # models that rejected response_format json_schema this process


class LLM:
    def __init__(self, conn: sqlite3.Connection, run_id: str | None = None, concurrency: int | None = None):
        self.cache = LLMCache(conn)
        self.run_id = run_id
        self.sem = asyncio.Semaphore(concurrency or settings.concurrency)
        self._client: anthropic.AsyncAnthropic | None = None
        self._http: httpx.AsyncClient | None = None

    @property
    def client(self) -> anthropic.AsyncAnthropic:
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(
                api_key=os.environ.get("ANTHROPIC_API_KEY"),
                base_url=settings.anthropic_base_url,
                max_retries=4,
                timeout=600,
            )
        return self._client

    async def structured(self, role: str, system: str, user: str, schema: type[T], stage: str) -> T:
        cfg = settings.role(role)
        json_schema = strict_schema(schema)
        key = cache_key(model=cfg.model, effort=cfg.effort, thinking=cfg.thinking, budget=cfg.thinking_budget,
                        system=system, user=user, schema=json_schema)

        hit = self.cache.get(key)
        if hit is not None:
            try:
                out = schema.model_validate_json(hit["response"])
                self.cache.log_call(self.run_id, stage, cfg.model, True, 0, 0, 0.0, 0)
                return out
            except ValidationError:
                pass  # schema changed since this was cached; fall through and re-ask
        if settings.offline or RUNTIME["offline"]:
            raise LLMOffline(f"cache miss in offline mode ({stage})")

        async with self.sem:
            t0 = time.perf_counter()
            text, tin, tout, cost = await self._call(cfg, system, user, json_schema)
            try:
                out = schema.model_validate_json(text)
            except ValidationError as err:
                repair = (f"{user}\n\n---\nYour previous answer failed schema validation:\n{err}\n\n"
                          f"Previous answer:\n{text}\n\nReturn the corrected JSON only.")
                text, tin2, tout2, cost2 = await self._call(cfg, system, repair, json_schema)
                tin, tout, cost = tin + tin2, tout + tout2, cost + cost2
                out = schema.model_validate_json(text)  # second failure propagates
            latency = int((time.perf_counter() - t0) * 1000)

        self.cache.put(key, cfg.model, out.model_dump_json(), tin, tout)
        self.cache.log_call(self.run_id, stage, cfg.model, False, tin, tout, cost, latency)
        return out

    async def _call(self, cfg, system: str, user: str, json_schema: dict) -> tuple[str, int, int, float]:
        if settings.provider == "anthropic":
            return await self._call_anthropic(cfg, system, user, json_schema)
        return await self._call_openai(cfg, system, user, json_schema)

    @property
    def http(self) -> httpx.AsyncClient:
        if self._http is None:
            if not settings.openai_base_url or not os.environ.get("OPENAI_COMPAT_API_KEY"):
                raise LLMError("set OPENAI_COMPAT_BASE_URL and OPENAI_COMPAT_API_KEY (see .env.example)")
            self._http = httpx.AsyncClient(
                base_url=settings.openai_base_url.rstrip("/"), timeout=600,
                headers={"Authorization": f"Bearer {os.environ['OPENAI_COMPAT_API_KEY']}"})
        return self._http

    async def _call_openai(self, cfg, system: str, user: str, json_schema: dict) -> tuple[str, int, int, float]:
        body: dict[str, Any] = {
            "model": cfg.model,
            "messages": [
                {"role": "system", "content": system + "\n\nRespond with one JSON object only (no prose, no code "
                 "fences) matching this JSON Schema:\n" + json.dumps(json_schema, ensure_ascii=False)},
                {"role": "user", "content": user},
            ],
            "max_tokens": cfg.max_tokens,
            "temperature": 0,
            "enable_thinking": cfg.thinking,
        }
        if cfg.thinking and cfg.thinking_budget:
            body["thinking_budget"] = cfg.thinking_budget
        force_object = False
        for attempt in range(6):
            schema_mode = cfg.model not in _JSON_OBJECT_ONLY and not force_object
            body["response_format"] = ({"type": "json_schema", "json_schema": {"name": "output", "schema": json_schema,
                                                                               "strict": True}}
                                       if schema_mode else {"type": "json_object"})
            try:
                r = await self.http.post("/chat/completions", json=body)
            except httpx.TransportError:
                await asyncio.sleep(2 ** attempt)
                continue
            if r.status_code == 400 and schema_mode and "response_format" in r.text:
                _JSON_OBJECT_ONLY.add(cfg.model)  # e.g. deepseek-v4.1-flash
                continue
            if r.status_code == 400 and schema_mode and "grammar" in r.text:
                force_object = True  # server failed to compile the schema grammar for this input; Pydantic still checks
                continue
            if r.status_code in (408, 429, 500, 502, 503, 504):
                await asyncio.sleep(min(2 ** attempt, 30))
                continue
            if r.status_code != 200:
                raise LLMError(f"{cfg.model} HTTP {r.status_code}: {r.text[:300]}")
            break
        else:
            raise LLMError(f"{cfg.model}: retries exhausted")

        data = r.json()
        choice = data["choices"][0]
        if choice.get("finish_reason") == "content_filter":
            raise LLMRefusal(f"{cfg.model} declined the request")
        if choice.get("finish_reason") == "length":
            raise LLMError(f"{cfg.model} hit max_tokens={cfg.max_tokens}")
        text = (choice["message"].get("content") or "").strip()
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
        u = data.get("usage") or {}
        tin, tout = u.get("prompt_tokens", 0), u.get("completion_tokens", 0)
        return text, tin, tout, _cost(cfg.model, tin, tout)

    async def _call_anthropic(self, cfg, system: str, user: str, json_schema: dict) -> tuple[str, int, int, float]:
        output_config: dict[str, Any] = {"format": {"type": "json_schema", "schema": json_schema}}
        if cfg.effort:
            output_config["effort"] = cfg.effort
        kwargs: dict[str, Any] = dict(
            model=cfg.model,
            max_tokens=cfg.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            extra_body={"output_config": output_config},
        )
        if _is_5x(cfg.model):
            if settings.fallbacks:
                kwargs["extra_headers"] = {"anthropic-beta": "server-side-fallback-2026-07-01"}
                kwargs["extra_body"]["fallbacks"] = "default"
        else:
            kwargs["temperature"] = 0

        if cfg.max_tokens > 16000:
            async with self.client.messages.stream(**kwargs) as stream:
                resp = await stream.get_final_message()
        else:
            resp = await self.client.messages.create(**kwargs)

        if resp.stop_reason == "refusal":
            raise LLMRefusal(f"{cfg.model} declined the request")
        if resp.stop_reason == "max_tokens":
            raise LLMError(f"{cfg.model} hit max_tokens={cfg.max_tokens}")
        text = "".join(b.text for b in resp.content if b.type == "text")
        u = resp.usage
        tin = (u.input_tokens or 0) + (getattr(u, "cache_creation_input_tokens", 0) or 0)
        cache_read = getattr(u, "cache_read_input_tokens", 0) or 0
        tout = u.output_tokens or 0
        return text, tin + cache_read, tout, _cost(cfg.model, tin, tout, cache_read)


def usage_by_stage(conn: sqlite3.Connection, run_id: str | None = None) -> list[dict]:
    q = ("SELECT stage, COUNT(*) calls, SUM(cached) cached, SUM(tokens_in) tokens_in, SUM(tokens_out) tokens_out,"
         " ROUND(SUM(cost_usd), 4) cost_usd FROM llm_calls {} GROUP BY stage ORDER BY stage")
    rows = conn.execute(q.format("WHERE run_id=?" if run_id else ""), (run_id,) if run_id else ()).fetchall()
    return [dict(r) for r in rows]


if __name__ == "__main__":  # smoke test: python -m backend.llm
    from pydantic import BaseModel as _BM

    from .db import connect

    class Ping(_BM):
        ok: bool
        model_said: str

    async def _main() -> None:
        llm = LLM(connect(), run_id="smoke")
        for role in ("FAST", "CORE", "REASON"):
            out = await llm.structured(role, "Reply in JSON.", "Say hello in three words.", Ping, stage="smoke")
            print(role, settings.role(role).model, out)
        print(json.dumps(usage_by_stage(llm.cache.conn, "smoke"), indent=1))

    asyncio.run(_main())
