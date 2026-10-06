"""Stage 0b: threading.

1. Union-find over Message-ID / In-Reply-To / References (a missing parent still joins its children).
2. Fallback for broken threads: a component whose first message has no resolvable parent joins an earlier
   component with the same normalized subject, ≥ 50% participant overlap, within 14 days.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta

from .parse import ParsedEmail

_PREFIX_RE = re.compile(r"^\s*((re|fwd?|fw|aw|wg|sv|vs|tr|rv|antw)\s*(\[\d+\])?\s*:\s*)+", re.I)
_SUFFIX_RE = re.compile(r"\s*\((fwd|fw|forwarded)\)\s*$", re.I)

FALLBACK_WINDOW = timedelta(days=14)
FALLBACK_OVERLAP = 0.5


def normalize_subject(s: str) -> str:
    s = s or ""
    prev = None
    while prev != s:
        prev = s
        s = _PREFIX_RE.sub("", s)
        s = _SUFFIX_RE.sub("", s)
    return re.sub(r"\s+", " ", s).strip().casefold()


class _UF:
    def __init__(self):
        self.p: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def _participants(e: ParsedEmail) -> set[str]:
    return {a for a in [e.from_addr, *e.to_addrs, *e.cc_addrs] if a}


def build_threads(emails: list[ParsedEmail]) -> tuple[dict[str, str], list[dict]]:
    """Return (message_id -> thread_id, thread rows)."""
    uf = _UF()
    for e in emails:
        uf.find(e.message_id)
        for parent in [e.in_reply_to, *e.refs]:
            if parent:
                uf.union(parent, e.message_id)

    comps: dict[str, list[ParsedEmail]] = {}
    for e in emails:
        comps.setdefault(uf.find(e.message_id), []).append(e)
    for msgs in comps.values():
        msgs.sort(key=lambda m: m.sent_at)

    # subject fallback, processed in chronological order of each component's first message
    known = {e.message_id for e in emails}
    ordered = sorted(comps.items(), key=lambda kv: kv[1][0].sent_at)
    merged_into: dict[str, str] = {}
    by_subject: dict[str, list[str]] = {}
    for root, msgs in ordered:
        first = msgs[0]
        has_parent = any(p in known for p in [first.in_reply_to, *first.refs] if p)
        subj = normalize_subject(first.subject)
        target = None
        if not has_parent and subj:
            t_first = datetime.fromisoformat(first.sent_at)
            parts = _participants(first)
            for cand in reversed(by_subject.get(subj, [])):
                cmsgs = comps[cand]
                last = datetime.fromisoformat(cmsgs[-1].sent_at)
                if not (timedelta(0) <= t_first - last <= FALLBACK_WINDOW):
                    continue
                cparts = set().union(*(_participants(m) for m in cmsgs))
                if parts and len(parts & cparts) / len(parts) >= FALLBACK_OVERLAP:
                    target = cand
                    break
        if target is not None:
            comps[target].extend(msgs)
            comps[target].sort(key=lambda m: m.sent_at)
            merged_into[root] = target
        else:
            by_subject.setdefault(subj, []).append(root)
    for root in merged_into:
        comps.pop(root)

    mapping: dict[str, str] = {}
    rows = []
    for msgs in comps.values():
        tid = "T-" + hashlib.sha1(msgs[0].message_id.encode()).hexdigest()[:10]
        parts = sorted(set().union(*(_participants(m) for m in msgs)))
        for m in msgs:
            mapping[m.message_id] = tid
        rows.append({
            "thread_id": tid, "subject_norm": normalize_subject(msgs[0].subject),
            "first_at": msgs[0].sent_at, "last_at": msgs[-1].sent_at, "n_msgs": len(msgs),
            "participants": parts,
        })
    rows.sort(key=lambda r: r["first_at"])
    return mapping, rows
