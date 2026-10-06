from backend.models import Answer, Citation
from backend.pipeline.ask import _fts_query, _rrf, check_answer, confidence
from backend.pipeline.index import split_passages
from backend.render import redact


def test_passages_are_verbatim_and_bounded():
    text = "\n\n".join(["word " * 50, "Short para.", "Sentence one. " * 40])
    ps = split_passages(text, max_words=60)
    assert all(len(p.split()) <= 60 or "\n" not in p for p in ps)
    for p in ps:
        for chunk in p.split("\n\n"):
            assert chunk.strip() in text


def test_fts_query_and_rrf():
    assert _fts_query("Did we ever decide on a free tier?") == '"free" OR "tier"'
    assert _rrf(["a", "b"], ["b", "c"])[0] == "b"


def _ans(md, cites, status="found", ids=()):
    return Answer(status=status, answer_md=md, citations=[Citation(n=n, message_id=m, quote=q) for n, m, q in cites],
                  decision_ids=list(ids), confidence="high", caveats=[], closest=[])


def test_check_answer_flags_missing_and_unverifiable_citations():
    texts = {"<1@x>": ("We switch to Ledgerly on 6 July.", "")}
    rev = {"e1": "<1@x>"}
    cites, errors = check_answer(_ans("Ledgerly from 6 July [^1][^2].", [(1, "e1", "switch to Ledgerly")]),
                                 texts, rev, set())
    assert cites == [{"n": 1, "message_id": "<1@x>", "quote": "switch to Ledgerly"}]
    assert errors == ["marker [^2] has no citation"]
    _, errors = check_answer(_ans("x [^1]", [(1, "e1", "we switch to Stripe")]), texts, rev, set())
    assert errors and "not verbatim" in errors[0]


class _Conn:
    def __init__(self, types):
        self.types = types

    def execute(self, sql, args):
        return [(t,) for t in self.types]


def test_confidence_overlay_is_deterministic():
    two = [{"message_id": "<1>"}, {"message_id": "<2>"}]
    assert confidence(_Conn(["explicit"]), _ans("", [], ids=["DEC-1"]), two, []) == "high"
    assert confidence(_Conn(["implicit"]), _ans("", [], ids=["DEC-1"]), two, []) == "medium"
    assert confidence(_Conn(["explicit"]), _ans("", [], ids=["DEC-1"]), two[:1], []) == "medium"
    assert confidence(_Conn(["explicit"]), _ans("", [], ids=["DEC-1"]), two, ["bad quote"]) == "low"
    assert confidence(_Conn([]), _ans("", [], status="partial"), two, []) == "low"


def test_redaction_keeps_ids_and_numbers():
    out = redact({"message_id": "<a@b.example>", "quote": "mail ines@audit.example, EUR 18,000, +31 10 123 4567"})
    assert out["message_id"] == "<a@b.example>"
    assert out["quote"] == "mail [email], EUR 18,000, [phone]"


def test_citations_or_silence_drops_uncited_sentences():
    from backend.pipeline.ask import enforce_citations
    md = "We switch to Ledgerly on 6 July [^1]. It saves money. Helen agreed [^2]. Marta signed off [^3]."
    out, dropped = enforce_citations(md, {1, 2}, "found")
    assert out == "We switch to Ledgerly on 6 July [^1]. Helen agreed [^2]."
    assert dropped == 2
    out, dropped = enforce_citations("No decision was found on a free tier. Chloe proposed it [^1].", {1}, "found")
    assert out.startswith("No decision was found") and dropped == 0


def test_no_decision_status_detection():
    from backend.pipeline.ask import _NO_DECISION_RE
    assert _NO_DECISION_RE.match("No decision to rewrite the backend in Kotlin was made.")
    assert _NO_DECISION_RE.match("No decision was found to open a Lisbon office.")
    assert not _NO_DECISION_RE.match("We decided to switch providers.")
