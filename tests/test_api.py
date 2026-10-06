"""API contract tests against a small throwaway database (no model calls)."""
import json
import urllib.parse

import pytest
from fastapi.testclient import TestClient

from backend import app as app_mod
from backend.db import connect

MID1, MID2 = "<m1@x.example>", "<m2@x.example>"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    conn = connect(tmp_path / "api.db")
    conn.execute("INSERT INTO people(id, canonical_name, role_guess, org, is_internal) VALUES(1,'Helen Oyelaran','CFO','Acme',1)")
    for mid, text, at in [(MID1, "Approved: we contract Greg, capped at EUR 18,000. Call +31 10 123 4567.", "2026-02-26T10:38:00+00:00"),
                          (MID2, "Tomas says 1 hour was agreed.", "2026-04-09T09:00:00+00:00")]:
        conn.execute("INSERT INTO emails(message_id, thread_id, from_person_id, from_addr, from_name, to_addrs, cc_addrs,"
                     " sent_at, sent_tz, subject, new_text, quoted_text, fwd_text, body_raw, attachment_names)"
                     " VALUES(?,?,1,'helen@x.example','Helen',?,?,?,'+0100','Corvid',?,'','',?,'[]')",
                     (mid, "T-1", json.dumps(["dev@x.example"]), "[]", at, text, text))
    conn.execute("INSERT INTO clusters VALUES('C-1','Contractor',NULL,'Greg runs the migration.',1)")
    conn.execute("INSERT INTO decisions(decision_id, cluster_id, canonical_text, decided_by, decided_at, rationale,"
                 " alternatives, decision_type, status, authority_flag, authority_note, confidence)"
                 " VALUES('DEC-0001','C-1','Contract Greg with a EUR 18,000 cap','[\"Helen Oyelaran\"]','2026-02-26',"
                 " 'capacity','[\"agency\"]','explicit','contested',0,NULL,0.9)")
    conn.execute("INSERT INTO evidence(owner_kind, owner_id, message_id, quote, role, verified) VALUES"
                 " ('decision','DEC-0001',?, 'we contract Greg, capped at EUR 18,000','approval',1),"
                 " ('decision','DEC-0001',?, 'an unverified quote','approval',0)", (MID1, MID1))
    conn.execute("INSERT INTO conflicts VALUES('CON-001','C-1','SLA','Two versions')")
    conn.execute("INSERT INTO conflict_sides VALUES('CON-001','A','Lena','2 hours'), ('CON-001','B','Tomas','1 hour')")
    conn.execute("INSERT INTO evidence(owner_kind, owner_id, message_id, quote, role, verified) VALUES"
                 " ('conflict_side','CON-001:B',?, '1 hour was agreed','claim',1)", (MID2,))
    conn.commit()
    monkeypatch.setattr(app_mod, "CONN", conn)
    return TestClient(app_mod.app)


def test_read_endpoints(client):
    assert client.get("/api/health").json()["ok"]
    s = client.get("/api/stats").json()
    assert s["emails"] == 2 and s["decisions"] == 1 and s["decisions_by_status"] == {"contested": 1}
    lst = client.get("/api/decisions?status=contested,active").json()
    assert [d["decision_id"] for d in lst] == ["DEC-0001"]
    assert client.get("/api/decisions?status=superseded").json() == []
    card = client.get("/api/decisions/DEC-0001").json()
    assert [e["quote"] for e in card["evidence"]] == ["we contract Greg, capped at EUR 18,000"]  # unverified hidden
    assert card["conflict_ids"] == ["CON-001"] and card["current_state"] == "Greg runs the migration."
    assert client.get("/api/decisions/DEC-9999").status_code == 404
    conf = client.get("/api/conflicts").json()[0]
    assert conf["decision_id"] == "DEC-0001" and [s["side"] for s in conf["sides"]] == ["A", "B"]
    assert conf["sides"][1]["evidence"][0]["quote"] == "1 hour was agreed"
    assert client.get("/api/graph").json()["lanes"] == [{"cluster_id": "C-1", "topic": "Contractor"}]


def test_email_endpoint_accepts_encoded_ids_and_redacts(client):
    r = client.get("/api/emails/" + urllib.parse.quote(MID1, safe=""))
    assert r.status_code == 200 and r.json()["sender"] == "Helen Oyelaran"
    red = client.get("/api/emails/" + urllib.parse.quote(MID1, safe="") + "?redact=1").json()
    assert "[phone]" in red["new_text"] and red["message_id"] == MID1
    assert client.get("/api/emails/%3Cnope%40x%3E").status_code == 404


def test_write_endpoints(client):
    assert client.post("/api/decisions/DEC-0001/dispute", json={"note": "wrong cap"}).json() == {"ok": True}
    assert client.post("/api/ask", json={"question": "   "}).status_code == 400
    assert client.get("/api/runs/run-nope/events").status_code == 404
