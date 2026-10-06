"""Stage 2b: programmatic quote verification (no LLM).

Comparison is done on a normalised view (NFKC, unified quotes/dashes, collapsed whitespace, casefold), but what gets
stored is always the *original* span of the email text. So a verified quote is a plain substring of the cited
message's new_text or fwd_text; `is_verbatim` checks exactly that, and the UI only ever shows verified quotes.

Order of attempts for each quote:
1. exact (normalised) match in the cited message            -> verified
2. exact match in another message of the same thread        -> re-anchored to that message, counted as snapped
3. fuzzy match in the cited message (partial ratio >= 95)   -> snapped to the true span
4. otherwise                                                 -> dropped (verified = 0)
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

from rapidfuzz import fuzz

SNAP_THRESHOLD = 95

_TRANSLATE = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"', "″": '"', "«": '"', "»": '"',
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-", "−": "-",
    " ": " ", " ": " ", " ": " ",
})


def normalize_with_map(text: str) -> tuple[str, list[int]]:
    """Normalised string plus, for each of its characters, the index of the source character it came from."""
    out: list[str] = []
    idx: list[int] = []
    prev_space = True  # also strips leading whitespace
    for i, ch in enumerate(text):
        for c in unicodedata.normalize("NFKC", ch).translate(_TRANSLATE):
            if c == "…":
                c = "..."
            for cc in c.casefold():
                if cc.isspace():
                    if prev_space:
                        continue
                    cc, prev_space = " ", True
                else:
                    prev_space = False
                out.append(cc)
                idx.append(i)
    while out and out[-1] == " ":
        out.pop()
        idx.pop()
    return "".join(out), idx


def normalize(text: str) -> str:
    return normalize_with_map(text)[0]


def _span(text: str, idx: list[int], start: int, end: int) -> str:
    """Original substring covering normalised positions [start, end)."""
    return text[idx[start]: idx[end - 1] + 1]


def find_exact(quote: str, text: str) -> str | None:
    nq = normalize(quote).strip(" .,;:!?\"'-")
    if len(nq) < 3 or not text:
        return None
    nt, idx = normalize_with_map(text)
    pos = nt.find(nq)
    return None if pos < 0 else _span(text, idx, pos, pos + len(nq))


def find_fuzzy(quote: str, text: str, threshold: int = SNAP_THRESHOLD) -> str | None:
    nq = normalize(quote)
    if len(nq) < 12 or not text:
        return None
    nt, idx = normalize_with_map(text)
    al = fuzz.partial_ratio_alignment(nq, nt, score_cutoff=threshold)
    if al is None or al.dest_end <= al.dest_start:
        return None
    s, e = al.dest_start, al.dest_end
    while s > 0 and nt[s - 1].isalnum():  # snap outwards to whole words
        s -= 1
    while e < len(nt) and nt[e].isalnum():
        e += 1
    return _span(text, idx, s, e).strip()


def is_verbatim(quote: str, *texts: str) -> bool:
    return bool(quote) and any(quote in t for t in texts if t)


@dataclass
class QuoteStats:
    total: int = 0
    exact: int = 0
    snapped: int = 0
    reanchored: int = 0
    dropped: int = 0
    dropped_examples: list[str] = field(default_factory=list)

    def add(self, other: "QuoteStats") -> None:
        for k in ("total", "exact", "snapped", "reanchored", "dropped"):
            setattr(self, k, getattr(self, k) + getattr(other, k))
        self.dropped_examples = (self.dropped_examples + other.dropped_examples)[:20]

    def as_dict(self) -> dict:
        return {"quotes_total": self.total, "quotes_exact": self.exact, "quotes_snapped": self.snapped + self.reanchored,
                "quotes_reanchored": self.reanchored, "quotes_dropped": self.dropped}


@dataclass
class VerifiedQuote:
    message_id: str
    quote: str
    role: str
    verified: bool


def verify_quote(message_id: str, quote: str, role: str, texts: dict[str, tuple[str, str]],
                 stats: QuoteStats) -> VerifiedQuote:
    """texts: message_id -> (new_text, fwd_text) for every message the quote may legitimately come from."""
    stats.total += 1
    regions = texts.get(message_id, ("", ""))
    for region in regions:
        hit = find_exact(quote, region)
        if hit:
            stats.exact += 1
            return VerifiedQuote(message_id, hit, role, True)
    for other_id, other in texts.items():
        if other_id == message_id:
            continue
        for region in other:
            hit = find_exact(quote, region)
            if hit:
                stats.reanchored += 1
                return VerifiedQuote(other_id, hit, role, True)
    for region in regions:
        hit = find_fuzzy(quote, region)
        if hit:
            stats.snapped += 1
            return VerifiedQuote(message_id, hit, role, True)
    stats.dropped += 1
    stats.dropped_examples.append(quote[:120])
    return VerifiedQuote(message_id, quote, role, False)
