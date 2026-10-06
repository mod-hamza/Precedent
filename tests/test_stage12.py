from datetime import datetime, timezone

from backend.db import connect
from backend.models import DecisionRecord, Evidence, ExtractionResult, TriageMessage, TriageResult
from backend.pipeline.context import Msg, Thread
from backend.pipeline.extract import store_records
from backend.pipeline.triage import has_candidate
from backend.pipeline.verify import QuoteStats


def _tr(flag, *signals):
    return TriageResult(thread_id="t", has_candidate=flag,
                        messages=[TriageMessage(message_id=f"m{i}", signal=s, note="") for i, s in enumerate(signals, 1)])


def test_triage_rule_can_only_add_threads():
    assert has_candidate(_tr(False, "discussion", "approval"))
    assert has_candidate(_tr(False, "question", "decision"))
    assert has_candidate(_tr(True, "none"))  # model flag alone keeps it
    assert not has_candidate(_tr(False, "none", "discussion", "question"))


def _thread():
    dt = datetime(2026, 2, 26, 11, 38, tzinfo=timezone.utc)
    mk = lambda a, mid, text: Msg(a, mid, "Helen Oyelaran", "helen@x.example", [], dt, "s", text, "", None, "", False)
    return Thread("T-abc", "s", [mk("m1", "<1@x>", "Could we use Greg?"),
                                 mk("m2", "<2@x>", "Approved: we contract Greg, capped at EUR 18,000.")], [])


def _rec(quotes, date="2026-02-26"):
    return DecisionRecord(topic_label="Contractor", decision_text="Contract Greg", stance="final",
                          decision_type="explicit", decided_by=["Helen Oyelaran"], decision_date=date, rationale=None,
                          alternatives=[], conditions=None, overrides_hint=None, authority_note=None,
                          evidence=[Evidence(message_id=m, quote=q, role="approval") for m, q in quotes],
                          confidence=0.9)


def test_store_records_maps_aliases_verifies_and_discards(tmp_path):
    conn = connect(tmp_path / "t.db")
    res = ExtractionResult(records=[
        _rec([("m2", "we contract Greg, capped at EUR 18,000"), ("m1", "invented quote nobody wrote")], date="26/02"),
        _rec([("m1", "this quote does not exist anywhere")]),
    ])
    stats = QuoteStats()
    stored = store_records(conn, _thread(), res, stats)
    assert len(stored) == 1 and stored[0]["decision_date"] == "2026-02-26"  # invalid date -> decisive message date
    rows = conn.execute("SELECT message_id, quote, verified FROM evidence ORDER BY id").fetchall()
    assert [tuple(r) for r in rows] == [("<2@x>", "we contract Greg, capped at EUR 18,000", 1),
                                        ("<1@x>", "invented quote nobody wrote", 0)]
    assert stats.dropped == 2 and stats.exact == 1
