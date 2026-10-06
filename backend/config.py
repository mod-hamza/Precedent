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
    effort: str | None  # None = do not send output_config.effort (Haiku 4.5 rejects it)
    max_tokens: int


@dataclass(frozen=True)
class Settings:
    db_path: Path = field(default_factory=lambda: Path(_env("PRECEDENT_DB", str(ROOT / "data" / "precedent.db"))))
    corpus_dir: Path = field(default_factory=lambda: Path(_env("PRECEDENT_CORPUS", str(ROOT / "corpus" / "emails"))))
    # Explicit base URL so the app never inherits a gateway configured for some other tool via ANTHROPIC_BASE_URL.
    anthropic_base_url: str = field(default_factory=lambda: _env("PRECEDENT_ANTHROPIC_BASE_URL", "https://api.anthropic.com"))
    concurrency: int = field(default_factory=lambda: int(_env("PRECEDENT_CONCURRENCY", "8")))
    # Server-side refusal fallback (beta) on the 5.x models; set to 0 to disable.
    fallbacks: bool = field(default_factory=lambda: _env("PRECEDENT_FALLBACKS", "1") == "1")
    offline: bool = field(default_factory=lambda: _env("PRECEDENT_OFFLINE", "0") == "1")  # cache-only; demo mode
    embed_backend: str = field(default_factory=lambda: _env("PRECEDENT_EMBED", "auto"))  # auto|voyage|st|hash

    fast: RoleConfig = field(default_factory=lambda: RoleConfig(
        _env("PRECEDENT_FAST_MODEL", "claude-haiku-4-5-20251001"), None, int(_env("PRECEDENT_FAST_MAX_TOKENS", "4000"))))
    core: RoleConfig = field(default_factory=lambda: RoleConfig(
        _env("PRECEDENT_CORE_MODEL", "claude-sonnet-5-5"), _env("PRECEDENT_CORE_EFFORT", "medium"),
        int(_env("PRECEDENT_CORE_MAX_TOKENS", "16000"))))
    reason: RoleConfig = field(default_factory=lambda: RoleConfig(
        _env("PRECEDENT_REASON_MODEL", "claude-opus-5-5"), _env("PRECEDENT_REASON_EFFORT", "high"),
        int(_env("PRECEDENT_REASON_MAX_TOKENS", "32000"))))

    def role(self, name: str) -> RoleConfig:
        return {"FAST": self.fast, "CORE": self.core, "REASON": self.reason}[name]


settings = Settings()

# USD per million tokens (input, output). Cache reads are billed separately by the API; we log them at the input rate
# multiplied by 0.1, which matches current pricing closely enough for a cost panel.
PRICING: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5-20251001": (1.0, 5.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-opus-5-5": (4.0, 20.0),
}
