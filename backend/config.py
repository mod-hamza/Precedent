"""Runtime configuration. Everything is overridable via environment (or a .env file at the repo root)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv(ROOT / ".env")


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class RoleConfig:
    model: str
    effort: str | None  # anthropic only; None = do not send output_config.effort (Haiku 4.5 rejects it)
    max_tokens: int
    thinking: bool = True  # openai-compatible only: sent as enable_thinking
    thinking_budget: int | None = None  # openai-compatible only: caps reasoning tokens (latency control)


# provider -> role -> (model, effort, max_tokens, thinking, thinking_budget)
_ROLE_DEFAULTS = {
    # Hackathon Alibaba Cloud Model Studio (OpenAI-compatible). CORE and REASON are different model families so the
    # eval judge (REASON) is not the extractor (CORE); neither is GLM, which generated the synthetic corpus.
    # Uncapped reasoning on qwen3.8-max ran 1-11k tokens (30-300 s) per thread; a 2k cap gave identical records on a
    # spot check at ~26 s.
    "openai": {"FAST": ("qwen3.8-flash", None, 4000, False, None),
               "CORE": ("qwen3.8-max", None, 16000, True, 3000),
               "REASON": ("deepseek-v4-pro", None, 32000, True, 12000),
               # eval judge: a different model family from the extractor (PRD §11)
               "JUDGE": ("deepseek-v4-pro", None, 8000, True, 4000),
               # second pass for hard threads: CORE found nothing although triage saw a decision signal
               "CORE_DEEP": ("qwen3.8-max", None, 24000, True, 12000),
               # Ask-time answers, reasoning off: with citation enforcement in code, dev Q&A was 74-79% at p50 ~8.5 s
               # vs a mean of ~65% at ~16 s with a 2k reasoning budget (the holdout run used the 2k budget)
               "ANSWER": ("qwen3.8-max", None, 8000, False, None)},
    "anthropic": {"FAST": ("claude-haiku-4-5-20251001", None, 4000, False, None),
                  "CORE": ("claude-sonnet-5-5", "medium", 16000, True, None),
                  "REASON": ("claude-opus-5-5", "high", 32000, True, None),
                  "CORE_DEEP": ("claude-sonnet-5-5", "high", 24000, True, None),
                  "JUDGE": ("claude-opus-5-5", "medium", 8000, True, None),
                  "ANSWER": ("claude-sonnet-5-5", "low", 8000, True, None)},
}


def _role(provider: str, name: str) -> RoleConfig:
    model, effort, max_tokens, thinking, budget = _ROLE_DEFAULTS[provider][name]
    return RoleConfig(
        model=_env(f"PRECEDENT_{name}_MODEL", model),
        effort=_env(f"PRECEDENT_{name}_EFFORT", effort or "") or None,
        max_tokens=int(_env(f"PRECEDENT_{name}_MAX_TOKENS", str(max_tokens))),
        thinking=_env(f"PRECEDENT_{name}_THINKING", "1" if thinking else "0") == "1",
        thinking_budget=int(_env(f"PRECEDENT_{name}_THINKING_BUDGET", str(budget or 0))) or None,
    )


@dataclass(frozen=True)
class Settings:
    db_path: Path = field(default_factory=lambda: Path(_env("PRECEDENT_DB", str(ROOT / "data" / "precedent.db"))))
    corpus_dir: Path = field(default_factory=lambda: Path(_env("PRECEDENT_CORPUS", str(ROOT / "corpus" / "emails"))))
    provider: str = field(default_factory=lambda: _env("PRECEDENT_PROVIDER", "openai"))  # openai | anthropic
    openai_base_url: str = field(default_factory=lambda: _env("OPENAI_COMPAT_BASE_URL", ""))
    # Explicit base URL so the app never inherits a gateway configured for some other tool via ANTHROPIC_BASE_URL.
    anthropic_base_url: str = field(default_factory=lambda: _env("PRECEDENT_ANTHROPIC_BASE_URL", "https://api.anthropic.com"))
    concurrency: int = field(default_factory=lambda: int(_env("PRECEDENT_CONCURRENCY", "16")))
    # Server-side refusal fallback (beta) on the Claude 5.x models; set to 0 to disable.
    fallbacks: bool = field(default_factory=lambda: _env("PRECEDENT_FALLBACKS", "1") == "1")
    offline: bool = field(default_factory=lambda: _env("PRECEDENT_OFFLINE", "0") == "1")  # cache-only; demo mode
    embed_backend: str = field(default_factory=lambda: _env("PRECEDENT_EMBED", "auto"))  # auto|voyage|st|hash

    def role(self, name: str) -> RoleConfig:
        return _role(self.provider, name)


settings = Settings()

# USD per million tokens (input, output). Cache reads are logged at 0.1x the input rate.
# The hackathon Model Studio plan has no per-token price we can see, so those models log tokens at $0 unless
# PRECEDENT_PRICE_<MODEL>="in,out" is set (model name upper-cased, '.' and '-' -> '_').
PRICING: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5-20251001": (1.0, 5.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-opus-5-5": (4.0, 20.0),
}


def price(model: str) -> tuple[float, float]:
    override = os.environ.get("PRECEDENT_PRICE_" + model.upper().replace(".", "_").replace("-", "_"))
    if override:
        pin, pout = (float(x) for x in override.split(","))
        return pin, pout
    return PRICING.get(model, (0.0, 0.0))
