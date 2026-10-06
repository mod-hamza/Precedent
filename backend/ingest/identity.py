"""Stage 0c: identity resolution (PRD §7 Stage 0).

1. exact email address
2. normalized display name (casefold, strip accents/punctuation, token-set ratio ≥ 0.9) within the same domain
3. remaining ambiguous pairs (same-looking name, different domains) adjudicated by FAST with signatures as context;
   without an LLM, exact full-name matches are merged.
role_guess / org / is_internal are inferred from signatures and domains; the pipeline is never given an org chart.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from ..models import IdentityVerdict, RoleGuess
from .parse import ParsedEmail

NAME_RATIO = 90


def norm_name(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^\w\s]", " ", s.casefold())
    return re.sub(r"\s+", " ", s).strip()


def _domain(addr: str) -> str:
    return addr.split("@", 1)[1] if "@" in addr else ""


def _name_from_addr(addr: str) -> str:
    return " ".join(p.capitalize() for p in re.split(r"[._-]+", addr.split("@")[0]) if p)


@dataclass
class _Person:
    addrs: set[str] = field(default_factory=set)
    names: Counter = field(default_factory=Counter)

    @property
    def canonical(self) -> str:
        if not self.names:
            return _name_from_addr(sorted(self.addrs)[0])
        # most frequent, ties broken by the longer (more complete) name
        return max(self.names.items(), key=lambda kv: (len(kv[0].split()) >= 2, kv[1], len(kv[0])))[0]


def _similar(a: str, b: str) -> bool:
    na, nb = norm_name(a), norm_name(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    return len(na.split()) >= 2 and len(nb.split()) >= 2 and fuzz.token_set_ratio(na, nb) >= NAME_RATIO


def _signature_snippet(emails: list[ParsedEmail], addr: str) -> str:
    for e in emails:
        if e.from_addr == addr and e.body_raw:
            tail = [ln for ln in e.body_raw.strip().split("\n") if ln.strip()][-6:]
            return "\n".join(tail)
    return "(no email sent from this address)"


def _role_and_org(emails: list[ParsedEmail], addrs: set[str], name: str) -> tuple[str | None, str | None]:
    roles, orgs = Counter(), Counter()
    target = norm_name(name)
    for e in emails:
        if e.from_addr not in addrs:
            continue
        lines = [ln.strip() for ln in e.body_raw.split("\n")]
        for i, ln in enumerate(lines):
            if norm_name(ln) == target and i + 1 < len(lines):
                nxt = lines[i + 1]
                if not nxt or "@" in nxt or len(nxt) > 70 or re.search(r"\d{3}", nxt):
                    continue
                parts = [p.strip() for p in re.split(r",|\|", nxt) if p.strip()]
                # "Maya Chen\nLedgerly": a line that matches the sender's domain is the org, not a role
                squashed = re.sub(r"[^a-z0-9]", "", norm_name(parts[0]))
                label = re.sub(r"[^a-z0-9]", "", _domain(e.from_addr).split(".")[0])
                if squashed and label and (label in squashed or squashed in label):
                    orgs[parts[0]] += 1
                    continue
                roles[parts[0]] += 1
                if len(parts) > 1:
                    orgs[parts[1]] += 1
    role = roles.most_common(1)[0][0] if roles else None
    org = orgs.most_common(1)[0][0] if orgs else None
    return role, org


async def resolve_identities(emails: list[ParsedEmail], llm=None) -> tuple[list[dict], dict[str, int]]:
    """Return (people rows incl. identities, address -> person_id)."""
    # 1. exact address
    persons: dict[str, _Person] = {}
    for e in emails:
        for name, addr in [(e.from_name, e.from_addr), *e.to_named]:
            addr = addr.strip().lower()
            if not addr:
                continue
            p = persons.setdefault(addr, _Person({addr}))
            if name and "@" not in name:
                p.names[name.strip()] += 1

    groups: list[_Person] = list(persons.values())

    def merge(a: _Person, b: _Person) -> None:
        a.addrs |= b.addrs
        a.names.update(b.names)
        groups.remove(b)

    # 2. similar display name within the same domain
    changed = True
    while changed:
        changed = False
        for i, a in enumerate(groups):
            for b in groups[i + 1:]:
                if {_domain(x) for x in a.addrs} & {_domain(x) for x in b.addrs} and _similar(a.canonical, b.canonical):
                    merge(a, b)
                    changed = True
                    break
            if changed:
                break

    # 3. ambiguous cross-domain pairs
    pairs = [(a, b) for i, a in enumerate(groups) for b in groups[i + 1:]
             if len(norm_name(a.canonical).split()) >= 2 and _similar(a.canonical, b.canonical)]
    for a, b in pairs:
        if a not in groups or b not in groups:
            continue
        same = norm_name(a.canonical) == norm_name(b.canonical)
        if llm is not None:
            sa = _signature_snippet(emails, sorted(a.addrs)[0])
            sb = _signature_snippet(emails, sorted(b.addrs)[0])
            prompt = (f"Mailbox identity check. Are these two senders the same real person?\n\n"
                      f"A: {a.canonical} <{', '.join(sorted(a.addrs))}>\nLast lines of an email from A:\n{sa}\n\n"
                      f"B: {b.canonical} <{', '.join(sorted(b.addrs))}>\nLast lines of an email from B:\n{sb}")
            verdict = await llm.structured("FAST", "You resolve sender identities in a company mailbox. Be conservative.",
                                           prompt, IdentityVerdict, stage="identity")
            same = verdict.same_person
        if same:
            merge(a, b)

    # internal domain = most common sender domain
    sender_domains = Counter(_domain(e.from_addr) for e in emails if e.from_addr)
    internal = sender_domains.most_common(1)[0][0] if sender_domains else ""

    rows, addr_to_pid = [], {}
    groups.sort(key=lambda g: (not any(_domain(a) == internal for a in g.addrs), g.canonical.casefold()))
    for pid, g in enumerate(groups, start=1):
        name = g.canonical
        role, org = _role_and_org(emails, g.addrs, name)
        is_int = any(_domain(a) == internal for a in g.addrs)
        if not org:
            dom = next((_domain(a) for a in sorted(g.addrs) if _domain(a) == internal), _domain(sorted(g.addrs)[0]))
            org = dom.split(".")[0].replace("-", " ").title() if dom else None
        idents = [("email", a) for a in sorted(g.addrs)] + [("display_name", n) for n in sorted(g.names)]
        rows.append({"id": pid, "canonical_name": name, "role_guess": role, "org": org, "is_internal": int(is_int),
                     "identities": idents})
        for a in g.addrs:
            addr_to_pid[a] = pid
    if llm is not None:
        await infer_roles(emails, rows, groups, llm)
    return rows, addr_to_pid


ROLE_PROMPT = """You infer a person's job role at their company from emails they sent and emails sent to them. Judge from
behaviour: who approves what, who others ask for sign-off, what they are responsible for. Give a short job title
(e.g. "CEO", "Head of Sales") only if the emails make it reasonably clear; otherwise null."""


async def infer_roles(emails: list[ParsedEmail], rows: list[dict], groups: list[_Person], llm) -> None:
    """Internal people whose signatures show no role get one inferred from behaviour (marked as inferred)."""
    for row, g in zip(rows, groups):
        if row["role_guess"] or not row["is_internal"]:
            continue
        sent = [e for e in emails if e.from_addr in g.addrs and e.new_text.strip()]
        if len(sent) < 3:
            continue
        first = row["canonical_name"].split()[0]
        received = [e for e in emails if g.addrs & set(e.to_addrs) and re.search(rf"\b{re.escape(first)}\b",
                                                                                   e.new_text, re.I)]
        parts = [f"PERSON: {row['canonical_name']}", "", "SENT BY THEM:"]
        parts += [f"- {e.subject}: {e.new_text.strip()[:300]}" for e in sent[:8]]
        parts += ["", "SENT TO THEM BY OTHERS:"]
        parts += [f"- from {e.from_name}: {e.new_text.strip()[:300]}" for e in received[:8]]
        guess = await llm.structured("FAST", ROLE_PROMPT, "\n".join(parts), RoleGuess, stage="identity_role")
        if guess.role:
            row["role_guess"] = f"{guess.role} (inferred from behaviour)"
