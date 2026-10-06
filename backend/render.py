"""PII redaction at render time (PRD §10.6): mask email addresses, phone numbers and IBANs in API output.

Applied recursively to response payloads when the client asks for it (?redact=1). The stored data is untouched, so
quotes stay verifiable; only what is displayed is masked.
"""
from __future__ import annotations

import re
from typing import Any

_EMAIL = re.compile(r"(?<![\w.<])([\w.+-]{1,64})@([\w-]+\.)+[\w-]{2,}")
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){2,7}(?:\s?[A-Z0-9]{1,3})?\b")
_PHONE = re.compile(r"(?<![\w€$£])(?:\+\d{1,3}[\s.-]?)?(?:\(\d{1,4}\)[\s.-]?)?\d{2,4}(?:[\s.-]\d{2,4}){2,4}(?![\w%])")
_MSGID_KEYS = {"message_id", "id", "decision_id", "cluster_id", "conflict_id", "record_id", "thread_id"}


def redact_text(s: str) -> str:
    s = _IBAN.sub("[IBAN]", s)
    s = _EMAIL.sub("[email]", s)
    s = _PHONE.sub(lambda m: m.group(0) if len(re.sub(r"\D", "", m.group(0))) < 9 else "[phone]", s)
    return s


def redact(obj: Any, key: str | None = None) -> Any:
    if isinstance(obj, str):
        return obj if key in _MSGID_KEYS else redact_text(obj)
    if isinstance(obj, list):
        return [redact(v, key) for v in obj]
    if isinstance(obj, dict):
        return {k: redact(v, k) for k, v in obj.items()}
    return obj
