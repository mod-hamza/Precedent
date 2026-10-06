from pathlib import Path

import pytest

from backend.ingest.parse import parse_bytes, split_body, strip_signature
from backend.ingest.thread import build_threads, normalize_subject

ROOT = Path(__file__).resolve().parent.parent


def _eml(headers: dict, body: str) -> bytes:
    h = "\n".join(f"{k}: {v}" for k, v in headers.items())
    return (h + '\nContent-Type: text/plain; charset="UTF-8"\n\n' + body).encode("utf-8")


def test_quote_intro_and_signature():
    body = ("ok saturday then 👍\n\nCheers, Dev\nDev Raman\nCTO & co-founder, Parcelwise B.V.\n\n"
            "On 22 Jan 2026, Marta Kowalczyk wrote:\n> can we move the cutover to saturday?")
    new, quoted, fwd, meta = split_body(body, "Dev Raman", "dev@parcelwise.example")
    assert new == "ok saturday then 👍"
    assert "cutover" in quoted and fwd == "" and meta is None


def test_outlook_block_is_quoted():
    body = ("Approved, go with Ledgerly.\n\n-----Original Message-----\nFrom: Helen <helen@x.example>\n"
            "Sent: Mon, 2 Feb 2026\nTo: marta@x.example\nSubject: payments\n\nShall we go with Ledgerly?")
    new, quoted, _, _ = split_body(body, "Marta Kowalczyk", "marta@x.example")
    assert new == "Approved, go with Ledgerly."
    assert "Shall we go" in quoted


def test_forward_is_attributed_to_original_author():
    body = ("FYI see below.\n\nKind regards,\nKofi\n\n---------- Forwarded message ----------\n"
            "From: lena@parcelwise.example\nDate: Tue, 20 Jan 2026 11:02:00 +0100\nSubject: invoice batch\n\n"
            "the batch runs thursday this time.\n- lena\n\nRegards,\nKofi Mensah\nQA Contractor")
    new, _, fwd, meta = split_body(body, "Kofi Mensah", "kofi@parcelwise.example")
    assert new == "FYI see below."
    assert fwd.startswith("the batch runs thursday") and "Kofi Mensah" not in fwd
    assert meta["from_addr"] == "lena@parcelwise.example" and meta["date"].startswith("2026-01-20T10:02")


@pytest.mark.parametrize("last", ["Thanks, approved.", "ok saturday then", "send it.", "Marta here, approved."])
def test_short_final_decision_lines_survive(last):
    assert strip_signature(["Some context.", "", last], "Marta Kowalczyk", "marta@parcelwise.example")[-1] == last


def test_stacked_signoffs_are_removed():
    lines = ["Steps are in the ticket.", "", "Regards,", "", "Regards,", "Kofi Mensah", "QA Contractor"]
    assert strip_signature(lines, "Kofi Mensah", "kofi@parcelwise.example") == ["Steps are in the ticket."]
    lines = ["Tour promised.", "", "Best regards,", "Elena Voss", "", "Best regards,", "Elena Voss"]
    assert strip_signature(lines, "Elena Voss", "elena.voss@mailbox.example") == ["Tour promised."]
    lines = ["let's do it in may. 👍", "", "Sent from my iPhone", "", "M"]
    assert strip_signature(lines, "Marta Kowalczyk", "marta@parcelwise.example") == ["let's do it in may. 👍"]


def test_new_text_is_verbatim_substring_of_body():
    e = parse_bytes(_eml({"From": "Tomás Ibarra <tomas@parcelwise.example>", "To": "marta@parcelwise.example",
                          "Subject": "=?utf-8?q?Re=3A_Redline_renewal?=", "Date": "Wed, 11 Feb 2026 09:00:00 +0100",
                          "Message-ID": "<a@x>"},
                         "Offer is out: 15% for 2 years.\n\nSaludos!\nTomás Ibarra\nHead of Sales, Parcelwise"))
    assert e.subject == "Re: Redline renewal"
    assert e.new_text == "Offer is out: 15% for 2 years." and e.new_text in e.body_raw
    assert e.sent_at.startswith("2026-02-11T08:00") and e.sent_tz == "+0100"


def test_threading_union_find_and_subject_fallback():
    base = {"To": "b@x.example", "Date": "Mon, 05 Jan 2026 10:00:00 +0100"}
    root = parse_bytes(_eml({**base, "From": "a@x.example", "Subject": "Pricing", "Message-ID": "<1@x>"}, "q"))
    reply = parse_bytes(_eml({**base, "From": "b@x.example", "To": "a@x.example", "Subject": "Re: Pricing",
                              "Message-ID": "<2@x>", "In-Reply-To": "<1@x>"}, "a"))
    broken = parse_bytes(_eml({**base, "From": "a@x.example", "Subject": "Pricing (fwd)", "Message-ID": "<3@x>",
                               "Date": "Tue, 06 Jan 2026 10:00:00 +0100"}, "b"))
    other = parse_bytes(_eml({**base, "From": "z@y.example", "To": "q@y.example", "Subject": "Pricing",
                              "Message-ID": "<4@x>"}, "c"))
    mapping, rows = build_threads([root, reply, broken, other])
    assert mapping["<1@x>"] == mapping["<2@x>"] == mapping["<3@x>"]
    assert mapping["<4@x>"] != mapping["<1@x>"]  # same subject, no participant overlap
    assert normalize_subject("RE: AW: Fwd: Pricing (fwd)") == "pricing"


def test_pipeline_cannot_see_ground_truth():
    """PRD §5 isolation: nothing under backend/ references the eval-private data."""
    for p in (ROOT / "backend").rglob("*.py"):
        text = p.read_text(encoding="utf-8")
        assert "eval_private" not in text and "ground_truth" not in text and "manifest.csv" not in text, p
