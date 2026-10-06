"""Stage 0a: parse .eml / .mbox into structured emails and split each body into
new_text (the sender's own words), quoted_text (reply chains) and fwd_text (forwarded content).

No LLM. Evidence quotes are later verified as substrings of new_text ∪ fwd_text, so this module only ever
*cuts* text into regions; it never rewrites characters inside a region.
"""
from __future__ import annotations

import email
import hashlib
import json
import mailbox
import re
from dataclasses import asdict, dataclass, field
from datetime import timezone
from email import policy
from email.utils import getaddresses, parsedate_to_datetime
from pathlib import Path

# ---------------------------------------------------------------- markers
_FWD_RE = re.compile(r"^\s*(-{2,}\s*(Forwarded message|Original forwarded message|Weitergeleitete Nachricht|"
                     r"Mensaje reenviado|Doorgestuurd bericht)\s*-{2,}|Begin forwarded message:)\s*$", re.I)
_ORIG_RE = re.compile(r"^\s*-{3,}\s*(Original Message|Ursprüngliche Nachricht|Mensaje original|"
                      r"Oorspronkelijk bericht)\s*-{3,}\s*$", re.I)
_INTRO_RE = re.compile(
    r"^\s*(On\s.{4,160}\swrote|Am\s.{4,160}\sschrieb|El\s.{4,160}\sescribió|Le\s.{4,160}\sa écrit|"
    r"Op\s.{4,160}\sschreef)\s*:\s*$", re.I)
_HDR_RE = re.compile(r"^\s*(From|Von|De|Van|Sent|Gesendet|Enviado|Verzonden|Date|Datum|Fecha|To|An|Para|Aan|Cc|"
                     r"Subject|Betreff|Asunto|Onderwerp)\s*:", re.I)
_FROM_HDR = re.compile(r"^\s*(From|Von|De|Van)\s*:", re.I)

# a short mobile footer, possibly with a word before it or a quip after it ("dzięki. sent from my iPhone",
# "Sent from my phone. typos are free of charge.")
_MOBILE_RE = re.compile(r"^.{0,20}?\b(Sent from my \w+|Sent from (Outlook|Mail) for \w+|Get Outlook for \w+|"
                        r"Von meinem \w+ gesendet|Enviado desde mi \w+)\b.{0,50}$", re.I)
_DISCLAIMER_RE = re.compile(r"^\s*(CONFIDENTIALITY|DISCLAIMER|This (e-?mail|message)( and any attachments?)? "
                            r"(is|are|may be) (confidential|intended))", re.I)
_CLOSINGS = ["best", "best regards", "best wishes", "kind regards", "warm regards", "warmest regards", "regards",
             "many thanks", "thanks", "thank you", "thx", "cheers", "warmly", "sincerely", "yours", "yours sincerely",
             "yours faithfully", "yours truly", "all the best", "saludos", "un saludo", "danke", "viele grüße",
             "liebe grüße", "lg", "mfg", "met vriendelijke groet", "groetjes", "groeten", "groet", "br",
             "speak soon", "talk soon"]
# longest first, otherwise "best" wins over "best regards" and leaves "regards" as trailing text
_CLOSING_RE = re.compile(r"^\s*(" + "|".join(sorted(_CLOSINGS, key=len, reverse=True)) + r")"
                         r"\s*[,.!]*\s*(?P<rest>.*?)\s*[,.!]*\s*$", re.I)
# what may follow a closing word on the same line; anything else ("Thanks, approved.") is content, not a sign-off
_CLOSING_REST = {"", "so much", "again", "all", "everyone", "team", "in advance", "a lot", "very much",
                 "for your patience", "for your help", "for reading"}


@dataclass
class ParsedEmail:
    message_id: str
    in_reply_to: str | None
    refs: list[str]
    from_addr: str
    from_name: str
    to_addrs: list[str]
    cc_addrs: list[str]
    to_named: list[tuple[str, str]]  # (display name, address) for identity resolution
    sent_at: str  # ISO-8601 UTC
    sent_tz: str | None
    subject: str
    new_text: str
    quoted_text: str
    fwd_text: str
    fwd_meta: dict | None
    body_raw: str
    attachment_names: list[str] = field(default_factory=list)
    source_file: str = ""

    def row(self) -> dict:
        d = asdict(self)
        d.pop("to_named")
        for k in ("refs", "to_addrs", "cc_addrs", "attachment_names"):
            d[k] = json.dumps(d[k], ensure_ascii=False)
        d["fwd_meta"] = json.dumps(d["fwd_meta"], ensure_ascii=False) if d["fwd_meta"] else None
        return d


# ---------------------------------------------------------------- body extraction
def _html_to_text(html: str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "head"]):
        t.decompose()
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for li in soup.find_all("li"):
        li.insert_before("\n- ")
    for blk in soup.find_all(["p", "div", "tr", "h1", "h2", "h3", "h4", "blockquote"]):
        blk.insert_after("\n")
    for bq in soup.find_all("blockquote"):  # HTML quoting -> '>' lines so the splitter sees them
        bq.replace_with("\n".join("> " + ln for ln in bq.get_text().splitlines()) + "\n")
    text = soup.get_text()
    return re.sub(r"\n{3,}", "\n\n", text)


def _body_text(msg: email.message.EmailMessage) -> str:
    part = msg.get_body(preferencelist=("plain", "html"))
    if part is None:
        return ""
    try:
        content = part.get_content()
    except (LookupError, UnicodeDecodeError):
        payload = part.get_payload(decode=True) or b""
        content = payload.decode("utf-8", errors="replace")
    if part.get_content_subtype() == "html":
        content = _html_to_text(content)
    return content.replace("\r\n", "\n").replace("\r", "\n")


# ---------------------------------------------------------------- splitting
def _strip_trailing_blank(lines: list[str]) -> list[str]:
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def _signoff_tokens(name: str, addr: str) -> set[str]:
    toks = set()
    parts = [p for p in re.split(r"\s+", name.strip()) if p]
    if parts:
        toks |= {parts[0].casefold(), parts[0][0].casefold(), name.strip().casefold()}
    local = addr.split("@")[0].split(".")[0] if addr else ""
    if local:
        toks.add(local.casefold())
    return toks


def strip_signature(lines: list[str], sender_name: str = "", sender_addr: str = "") -> list[str]:
    """Cut a trailing signature / sign-off / mobile footer / disclaimer. Only removes whole trailing lines."""
    lines = list(lines)
    # 1. RFC 3676 sig delimiter "-- "
    for i, ln in enumerate(lines):
        if ln.rstrip() in ("--", "-- ") and i > 0:
            lines = lines[:i]
            break
    # 2. disclaimers: cut from the first disclaimer paragraph
    for i, ln in enumerate(lines):
        if _DISCLAIMER_RE.match(ln):
            lines = lines[:i]
            break
    _strip_trailing_blank(lines)
    toks = _signoff_tokens(sender_name, sender_addr)

    def is_name_line(s: str) -> bool:
        raw = s.strip().lstrip("-—–~ ").rstrip(".!, ")
        low = raw.casefold()
        if not low or len(low) > 40:
            return False
        if low in toks:
            return True
        words = raw.split()  # "Kofi Mensah", "Parcelwise Support": capitalised, short, contains the sender's name
        return len(words) <= 3 and any(w.casefold() in toks for w in words) and all(w[:1].isupper() for w in words)

    def is_closing(s: str) -> bool:
        m = _CLOSING_RE.match(s)
        return bool(m) and (m.group("rest").casefold() in _CLOSING_REST or m.group("rest").casefold() in toks)

    # Iterate: generated mail often has a sign-off *and* an appended signature ("Regards," twice, then "Kofi").
    while True:
        before = len(lines)
        # 3. mobile footers at the very end
        while lines and _MOBILE_RE.match(lines[-1]):
            lines.pop()
            _strip_trailing_blank(lines)
        # 4. closing salutation, then nothing or a name block (name / title / company): "Regards," / "Kofi Mensah" / "QA"
        #    The tail must start with the sender's name so a short final line like "ok saturday then" is never cut.
        for i in range(len(lines) - 1, max(-1, len(lines) - 7), -1):
            if is_closing(lines[i]):
                tail = [t for t in lines[i + 1:] if t.strip()]
                if not tail or (is_name_line(tail[0]) and len(tail) <= 4 and all(len(t.strip()) <= 70 for t in tail)):
                    lines = lines[:i]
                    _strip_trailing_blank(lines)
                break
        # 5. bare name block: "M", "— Samir", "- lena", or "Greg" / "Ferrante Ops BV" / "sent from my phone, sorry..."
        for i in range(len(lines) - 1, max(-1, len(lines) - 5), -1):
            if is_name_line(lines[i]):
                tail = [t for t in lines[i + 1:] if t.strip()]
                if len(tail) <= 3 and all(len(t.strip()) <= 70 for t in tail):
                    lines = lines[:i]
                    _strip_trailing_blank(lines)
                break
        if len(lines) == before:
            return lines


def _parse_fwd_header(block: list[str]) -> tuple[dict, int]:
    """Parse 'From:/Date:/Subject:/To:' lines at the top of a forwarded block. Returns (meta, body_start)."""
    meta: dict = {}
    i = 0
    while i < len(block) and not block[i].strip():
        i += 1
    while i < len(block) and _HDR_RE.match(block[i]):
        k, v = block[i].split(":", 1)
        k = k.strip().casefold()
        v = v.strip()
        if k in ("from", "von", "de", "van"):
            addrs = getaddresses([v])
            name, addr = addrs[0] if addrs else ("", v)
            meta["from_name"], meta["from_addr"] = name, addr.lower()
        elif k in ("date", "datum", "fecha", "sent", "gesendet", "enviado", "verzonden"):
            meta["date_raw"] = v
            try:
                meta["date"] = parsedate_to_datetime(v).astimezone(timezone.utc).isoformat()
            except (TypeError, ValueError):
                pass
        elif k in ("subject", "betreff", "asunto", "onderwerp"):
            meta["subject"] = v
        i += 1
    return meta, i


def _find_outlook_header(lines: list[str], start: int) -> int | None:
    """An Outlook-style quoted header without the '-----Original Message-----' line: From: then Sent:/Date: and
    Subject: within the next few lines."""
    for i in range(start, len(lines)):
        if _FROM_HDR.match(lines[i]):
            window = " ".join(lines[i + 1:i + 6]).casefold()
            if ("sent:" in window or "date:" in window or "gesendet:" in window) and \
                    ("subject:" in window or "betreff:" in window):
                return i
    return None


def split_body(body: str, sender_name: str = "", sender_addr: str = "") -> tuple[str, str, str, dict | None]:
    """Return (new_text, quoted_text, fwd_text, fwd_meta)."""
    lines = body.split("\n")
    cut, kind = None, None
    for i, ln in enumerate(lines):
        if _FWD_RE.match(ln):
            cut, kind = i, "fwd"
            break
        if _ORIG_RE.match(ln):
            cut, kind = i, "quote"
            break
        if _INTRO_RE.match(ln) or (i + 1 < len(lines) and _INTRO_RE.match(ln + " " + lines[i + 1].strip())
                                   and not _INTRO_RE.match(lines[i + 1])):
            cut, kind = i, "quote"
            break
    outlook = _find_outlook_header(lines, 0)
    if outlook is not None and (cut is None or outlook < cut):
        cut, kind = outlook, "quote"

    head = lines if cut is None else lines[:cut]
    tail = [] if cut is None else lines[cut:]

    # '>' lines in the head (inline quoting without an intro line) are quoted, not new
    quoted_inline = [ln for ln in head if ln.lstrip().startswith(">")]
    head = [ln for ln in head if not ln.lstrip().startswith(">")]

    new_lines = strip_signature(_strip_trailing_blank(head), sender_name, sender_addr)
    new_text = "\n".join(new_lines).strip("\n")

    fwd_text, fwd_meta, quoted_parts = "", None, []
    if quoted_inline:
        quoted_parts.append("\n".join(quoted_inline))
    if kind == "fwd":
        block = tail[1:]
        fwd_meta, start = _parse_fwd_header(block)
        fbody = block[start:]
        # a reply chain inside the forwarded message stays quoted
        inner_cut = next((j for j, ln in enumerate(fbody) if _ORIG_RE.match(ln) or _INTRO_RE.match(ln)), None)
        if inner_cut is not None:
            quoted_parts.append("\n".join(fbody[inner_cut:]))
            fbody = fbody[:inner_cut]
        # the forwarder's own signature is appended after the forwarded block
        fbody = strip_signature(_strip_trailing_blank(fbody), sender_name, sender_addr)
        fwd_text = "\n".join(fbody).strip("\n")
        fwd_meta = fwd_meta or {}
    elif kind == "quote":
        quoted_parts.append("\n".join(tail).strip("\n"))
    return new_text, "\n\n".join(p for p in quoted_parts if p), fwd_text, fwd_meta


# ---------------------------------------------------------------- headers
def _clean_id(v: str | None) -> str | None:
    if not v:
        return None
    m = re.search(r"<[^>]+>", v)
    return m.group(0).strip() if m else v.strip()


def _addr_list(msg, name: str) -> list[tuple[str, str]]:
    vals = msg.get_all(name, [])
    return [(n.strip(), a.strip().lower()) for n, a in getaddresses([str(v) for v in vals]) if a.strip()]


def parse_message(msg: email.message.EmailMessage, source_file: str = "") -> ParsedEmail:
    from_list = _addr_list(msg, "From")
    from_name, from_addr = from_list[0] if from_list else ("", "")
    to = _addr_list(msg, "To")
    cc = _addr_list(msg, "Cc")
    subject = str(msg.get("Subject", "") or "").strip()

    date_hdr = msg.get("Date")
    try:
        dt = parsedate_to_datetime(str(date_hdr))
        sent_tz = dt.strftime("%z") or None
        sent_at = dt.astimezone(timezone.utc).isoformat() if dt.tzinfo else dt.replace(tzinfo=timezone.utc).isoformat()
    except (TypeError, ValueError):
        sent_at, sent_tz = "1970-01-01T00:00:00+00:00", None

    body = _body_text(msg)
    new_text, quoted_text, fwd_text, fwd_meta = split_body(body, from_name, from_addr)

    mid = _clean_id(msg.get("Message-ID"))
    if not mid:
        h = hashlib.sha1(f"{from_addr}|{sent_at}|{subject}|{body[:200]}".encode()).hexdigest()[:20]
        mid = f"<generated.{h}@precedent.local>"
    refs = re.findall(r"<[^>]+>", str(msg.get("References", "") or ""))

    attachments = [p.get_filename() for p in msg.iter_attachments() if p.get_filename()]
    return ParsedEmail(
        message_id=mid, in_reply_to=_clean_id(msg.get("In-Reply-To")), refs=refs,
        from_addr=from_addr, from_name=from_name,
        to_addrs=[a for _, a in to], cc_addrs=[a for _, a in cc], to_named=to + cc,
        sent_at=sent_at, sent_tz=sent_tz, subject=subject,
        new_text=new_text, quoted_text=quoted_text, fwd_text=fwd_text, fwd_meta=fwd_meta,
        body_raw=body, attachment_names=attachments, source_file=source_file,
    )


def parse_bytes(data: bytes, source_file: str = "") -> ParsedEmail:
    msg = email.message_from_bytes(data, policy=policy.default)
    return parse_message(msg, source_file)


def iter_path(path: Path):
    """Yield ParsedEmail from a .eml file, an .mbox file, a .zip, or a directory of those."""
    import zipfile

    path = Path(path)
    if path.is_dir():
        for p in sorted(path.rglob("*")):
            if p.is_file() and p.suffix.lower() in (".eml", ".mbox", ".zip"):
                yield from iter_path(p)
    elif path.suffix.lower() == ".eml":
        yield parse_bytes(path.read_bytes(), path.name)
    elif path.suffix.lower() == ".mbox":
        for i, m in enumerate(mailbox.mbox(str(path), factory=None)):
            yield parse_bytes(m.as_bytes(), f"{path.name}#{i}")
    elif path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as zf:
            for name in sorted(zf.namelist()):
                if name.lower().endswith(".eml"):
                    yield parse_bytes(zf.read(name), name)
