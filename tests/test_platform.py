import pytest
from fastapi.testclient import TestClient

from app.seed import COMPANY_VAN, UNKNOWN_CAR

KEY = "test-key"
AUTH = {"Authorization": f"Bearer {KEY}"}


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PLATFORM_API_KEY", KEY)
    monkeypatch.delenv("RELEASE", raising=False)
    from main import app

    with TestClient(app, headers=AUTH) as client:
        yield client


def synced(api):
    """Returns the IT, matching-fuel and unknown-car invoices, in demo order."""
    invoices = api.post("/api/ksef/sync").json()
    assert len(invoices) == 3
    return invoices


def post(api, invoice_id, **overrides):
    body = {
        "account": "402", "vat_deduction_percent": 100, "rationale": "Usługa IT",
        "confidence": 0.95, "actor": "invoice_agent", "source": "rule",
    }
    return api.post(f"/api/invoices/{invoice_id}/postings", json={**body, **overrides})


def test_seed_has_the_precedent_and_no_pending_invoices(api):
    assert [v["plate"] for v in api.get("/api/client").json()["fleet"]] == [COMPANY_VAN]
    invoices = api.get("/api/invoices").json()
    assert [i["status"] for i in invoices] == ["posted"]
    posting = api.get(f"/api/invoices/{invoices[0]['id']}").json()["postings"][0]
    assert (posting["account"], posting["vat_deduction_percent"], posting["reusable"]) == ("403", 50, True)


def test_ksef_sync_adds_nothing_the_second_time(api):
    synced(api)
    assert api.post("/api/ksef/sync").json() == []


def test_full_demo_scenario(api):
    it, fuel, unknown = synced(api)

    # 1. The IT invoice has no precedent, so the invoice agent posts it directly.
    assert api.get(f"/api/invoices/{it['id']}/precedents").json() == []
    assert post(api, it["id"]).status_code == 201

    # 2. The similar fuel invoice reuses the precedent and cites it.
    match = api.get(f"/api/invoices/{fuel['id']}/precedents").json()[0]
    assert match["applicable"] is True
    precedent_id = match["precedent"]["id"]
    posted = post(
        api, fuel["id"], account="403", vat_deduction_percent=50, source="precedent",
        precedent_id=precedent_id, rationale="Jak w precedensie",
    ).json()
    assert posted["precedent_id"] == precedent_id
    assert posted["deductible_vat"] == "34.50"

    # 3. The same seller with an unknown car must not reuse it, even if an agent tries.
    match = api.get(f"/api/invoices/{unknown['id']}/precedents").json()[0]
    assert match["score"] > 0.5
    assert match["applicable"] is False
    assert UNKNOWN_CAR in match["blockers"][0]
    refused = post(
        api, unknown["id"], account="403", vat_deduction_percent=50, source="precedent", precedent_id=precedent_id,
    )
    assert refused.status_code == 409

    case = api.post(f"/api/invoices/{unknown['id']}/escalate", json={"reason": "Auto spoza floty"}).json()
    question = api.post(f"/api/cases/{case['id']}/questions", json={"text": "Do którego auta był ten zakup?"}).json()
    assert api.get(f"/api/cases/{case['id']}").json()["status"] == "waiting_for_client"
    assert [q["id"] for q in api.get("/api/questions", params={"status": "open"}).json()] == [question["id"]]

    decision = {
        "account": "403", "vat_deduction_percent": 50, "rationale": "Firmowe auto w użytku mieszanym",
        "confidence": 0.9, "actor": "regulations_agent", "source": "regulation",
        "legal_basis": "Art. 86a ust. 1 ustawy o VAT", "reusable": True, "conditions": {"vehicle_usage": "mixed"},
    }
    # The agent can't decide before the client has answered.
    assert api.post(f"/api/invoices/{unknown['id']}/postings", json=decision).status_code == 409

    api.post(f"/api/questions/{question['id']}/answer", json={"answer": "Firmowe, użytek mieszany"})
    assert api.get(f"/api/cases/{case['id']}").json()["status"] == "open"
    api.put("/api/client/vehicles", json={"plate": "dw 9876c", "model": "Skoda Octavia", "usage": "mixed"})
    new_precedent = api.post(f"/api/invoices/{unknown['id']}/postings", json=decision)
    assert new_precedent.status_code == 201
    assert api.get(f"/api/cases/{case['id']}").json()["status"] == "resolved"

    # The accountant corrects one decision and sees it replaced on the timeline.
    corrected = api.post(
        f"/api/postings/{new_precedent.json()['id']}/correct",
        json={"account": "403", "vat_deduction_percent": 100, "rationale": "Pojazd wyłącznie firmowy"},
    ).json()
    assert corrected["source"] == "accountant"
    postings = api.get(f"/api/invoices/{unknown['id']}").json()["postings"]
    assert [p["status"] for p in postings] == ["superseded", "active"]

    types = [e["type"] for e in api.get("/api/events").json()]
    for expected in ("invoice_posted", "case_opened", "question_asked", "question_answered", "precedent_created", "posting_corrected"):
        assert expected in types


def test_superseded_precedent_is_no_longer_offered(api):
    _, fuel, _ = synced(api)
    match = api.get(f"/api/invoices/{fuel['id']}/precedents").json()[0]
    api.post(
        f"/api/postings/{match['precedent']['id']}/correct",
        json={"account": "403", "vat_deduction_percent": 100, "rationale": "Korekta"},
    )
    assert api.get(f"/api/invoices/{fuel['id']}/precedents").json() == []
    refused = post(api, fuel["id"], source="precedent", precedent_id=match["precedent"]["id"], account="403")
    assert refused.status_code == 409


def test_guards_on_posting(api):
    it, _, _ = synced(api)
    assert post(api, it["id"], account="999").status_code == 422
    assert post(api, it["id"], source="regulation").status_code == 422
    assert post(api, it["id"], source="accountant").status_code == 422
    assert post(api, it["id"], source="precedent").status_code == 422
    assert post(api, it["id"]).status_code == 201
    assert post(api, it["id"]).status_code == 409


def test_rule_posting_is_refused_on_an_escalated_invoice(api):
    it, _, _ = synced(api)
    api.post(f"/api/invoices/{it['id']}/escalate", json={"reason": "Niejasne"})
    assert post(api, it["id"]).status_code == 409


def test_take_over_locks_agents_out(api):
    it, _, _ = synced(api)
    case = api.post(f"/api/invoices/{it['id']}/escalate", json={"reason": "Niejasne"}).json()
    api.post(f"/api/cases/{case['id']}/take-over")
    legal = {"source": "regulation", "legal_basis": "x", "actor": "regulations_agent"}
    assert post(api, it["id"], **legal).status_code == 409
    assert post(api, it["id"], source="accountant", actor="accountant").status_code == 201


def test_invoice_amounts_must_add_up(api):
    body = {
        "ksef_number": "x", "seller_name": "a", "seller_nip": "1", "description": "d",
        "net": "1.00", "vat": "0.23", "gross": "9.99", "issue_date": "2026-11-05",
    }
    assert api.post("/api/invoices", json=body).status_code == 422


def test_writes_need_the_key_and_reads_do_not(api):
    assert api.post("/api/ksef/sync", headers={"Authorization": ""}).status_code == 401
    assert api.post("/api/ksef/sync", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert api.get("/api/invoices", headers={"Authorization": ""}).status_code == 200


def test_reset_restores_the_seed(api):
    synced(api)
    assert api.post("/api/demo/reset").status_code == 204
    assert len(api.get("/api/invoices").json()) == 1
    assert len(synced(api)) == 3


def test_deployed_app_refuses_to_start_without_a_key(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RELEASE", "abc")
    monkeypatch.delenv("PLATFORM_API_KEY", raising=False)
    from main import app

    with pytest.raises(RuntimeError, match="PLATFORM_API_KEY"):
        with TestClient(app):
            pass
