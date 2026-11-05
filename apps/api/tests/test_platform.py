"""The platform through its HTTP contract, including the whole demo scenario."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from grok_invoices.seed import COMPANY_VAN, UNKNOWN_CAR, _fuel
from grok_invoices.domain.models import ReceivedDocument
from grok_invoices.service_layer import services


def synced(api):
    """Returns the IT, matching-fuel and unknown-car invoices, in demo order."""
    invoices = api.post("/api/ksef/sync", params={"source": "fixtures"}).json()
    assert len(invoices) == 3
    return invoices


def post(api, invoice_id, **overrides):
    body = {
        "account": "402", "vat_deduction_percent": 100, "rationale": "Usługa IT",
        "confidence": 0.95, "actor": "invoice_agent", "source": "rule",
    }
    return api.post(f"/api/invoices/{invoice_id}/postings", json={**body, **overrides})


def test_seed_has_the_precedent_and_no_pending_invoices(api):
    client = api.get("/api/client").json()
    assert [v["plate"] for v in client["fleet"]] == [COMPANY_VAN]
    assert UNKNOWN_CAR not in [v["plate"] for v in client["fleet"]]
    invoices = api.get("/api/invoices").json()
    assert [i["status"] for i in invoices] == ["posted"]
    posting = api.get(f"/api/invoices/{invoices[0]['id']}").json()["postings"][0]
    assert (posting["account"], posting["vat_deduction_percent"], posting["reusable"]) == ("403", 50, True)


def test_invoice_fields_come_from_the_parsed_ksef_document(api):
    _, _, unknown = synced(api)
    assert unknown["vehicle_plate"] == UNKNOWN_CAR
    assert (unknown["net"], unknown["vat"], unknown["gross"]) == ("200.00", "46.00", "246.00")
    assert unknown["seller_nip"] == "1132511471"
    assert "source_xml" not in unknown and "document" not in unknown

    detail = api.get(f"/api/invoices/{unknown['id']}").json()
    assert detail["document"]["body"]["additional_description"][0]["value"] == UNKNOWN_CAR
    xml = api.get(f"/api/invoices/{unknown['id']}/xml")
    assert xml.headers["content-type"].startswith("application/xml")
    assert UNKNOWN_CAR in xml.text


def test_ksef_sync_adds_nothing_the_second_time(api):
    synced(api)
    assert api.post("/api/ksef/sync", params={"source": "fixtures"}).json() == []


def test_full_demo_scenario(api):
    it, fuel, unknown = synced(api)

    # 1. The IT invoice has no precedent, so the invoice agent posts it directly.
    assert api.get(f"/api/invoices/{it['id']}/precedents").json() == []
    assert post(api, it["id"]).status_code == 201

    # 2. The fuel invoice for the fleet van reuses the precedent and cites it.
    match = api.get(f"/api/invoices/{fuel['id']}/precedents").json()[0]
    assert match["applicable"] is True
    precedent_id = match["precedent"]["id"]
    posted = post(
        api, fuel["id"], account="403", vat_deduction_percent=50, source="precedent",
        precedent_id=precedent_id, rationale="Jak w precedensie",
    ).json()
    assert posted["precedent_id"] == precedent_id
    assert posted["deductible_vat"] == "34.50"

    # 3. Same seller, same fuel, plate off the fleet: it must not reuse it, even if an agent tries.
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
    api.put("/api/client/vehicles", json={"plate": "gd 9r247", "model": "Skoda Octavia", "usage": "mixed"})
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


def test_accountant_override_replaces_the_precedent(api):
    _, fuel, _ = synced(api)
    old = api.get(f"/api/invoices/{fuel['id']}/precedents").json()[0]["precedent"]
    override = api.post(
        f"/api/postings/{old['id']}/correct",
        json={"account": "403", "vat_deduction_percent": 100, "rationale": "Korekta"},
    ).json()
    assert override["reusable"] is True
    assert override["conditions"] == old["conditions"]

    offered = api.get(f"/api/invoices/{fuel['id']}/precedents").json()
    assert [m["precedent"]["id"] for m in offered] == [override["id"]]
    refused = post(api, fuel["id"], source="precedent", precedent_id=old["id"], account="403")
    assert refused.status_code == 409


def test_guards_on_posting(api):
    it, _, _ = synced(api)
    assert post(api, it["id"], account="999").status_code == 422
    assert post(api, it["id"], source="regulation").status_code == 422
    assert post(api, it["id"], source="accountant").status_code == 422
    assert post(api, it["id"], source="precedent").status_code == 422
    assert post(api, it["id"], actor="client_agent").status_code == 422
    assert post(api, it["id"], source="regulation", legal_basis="x").status_code == 409
    assert post(api, it["id"]).status_code == 201
    assert post(api, it["id"]).status_code == 409


def test_a_vehicle_invoice_cannot_be_posted_by_plain_rule(api):
    _, fuel, unknown = synced(api)
    assert post(api, unknown["id"], account="403").status_code == 409
    assert post(api, fuel["id"], account="403").status_code == 409


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


def test_another_invoice_for_a_vehicle_in_question_is_held(api):
    _, _, unknown = synced(api)
    case = api.post(f"/api/invoices/{unknown['id']}/escalate", json={"reason": "Auto spoza floty"}).json()
    question = api.post(f"/api/cases/{case['id']}/questions", json={"text": "Które auto?"}).json()

    second = services.ingest_documents([
        ReceivedDocument("1132511471-20261106-DEMO-000005", _fuel("ON/2026/11/106", date(2026, 11, 6), UNKNOWN_CAR, "30"))
    ])[0]
    assert api.post(f"/api/invoices/{second.id}/escalate", json={"reason": "Znowu"}).status_code == 409
    match = api.get(f"/api/invoices/{second.id}/precedents").json()[0]
    assert match["applicable"] is False
    assert "waiting for the client's answer" in match["blockers"][0]

    api.post(f"/api/questions/{question['id']}/answer", json={"answer": "Firmowe"})
    decision = {
        "account": "403", "vat_deduction_percent": 50, "rationale": "Firmowe", "confidence": 0.9,
        "actor": "regulations_agent", "source": "regulation", "legal_basis": "Art. 86a",
        "reusable": True, "conditions": {"vehicle_plate": UNKNOWN_CAR},
    }
    new = api.post(f"/api/invoices/{unknown['id']}/postings", json=decision).json()

    # With the case closed, the next invoice for that car reuses the new precedent.
    match = next(m for m in api.get(f"/api/invoices/{second.id}/precedents").json() if m["precedent"]["id"] == new["id"])
    assert match["applicable"] is True


def test_unknown_fields_are_rejected_so_agent_mistakes_surface(api):
    it, _, _ = synced(api)
    assert post(api, it["id"], acount="402").status_code == 422
    assert post(api, it["id"], conditions={"plate": "X"}).status_code == 422


def test_writes_need_the_key_and_reads_do_not(api):
    assert api.post("/api/ksef/sync", params={"source": "fixtures"}, headers={"Authorization": ""}).status_code == 401
    assert api.post("/api/ksef/sync", params={"source": "fixtures"}, headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert api.get("/api/invoices", headers={"Authorization": ""}).status_code == 200


def test_public_reads_never_expose_the_client_phone(api, monkeypatch):
    monkeypatch.setenv("DEMO_CLIENT_PHONE", "+48123456789")
    api.post("/api/demo/reset")
    for response in (
        api.get("/api/client"),
        api.put("/api/client/vehicles", json={"plate": "X1", "model": "Y", "usage": "mixed"}),
        api.post("/api/client/facts", json={"key": "k", "value": "v"}),
    ):
        assert "+48123456789" not in response.text
        assert "phone" not in response.json()


def test_reset_restores_the_seed_but_event_ids_keep_counting(api):
    synced(api)
    last_event = api.get("/api/events").json()[-1]["id"]
    assert api.post("/api/demo/reset").status_code == 204
    invoices = api.get("/api/invoices").json()
    assert [i["id"] for i in invoices] == [1]
    events = api.get("/api/events").json()
    assert events[0]["type"] == "demo_reset"
    assert events[0]["id"] > last_event
    assert len(synced(api)) == 3


def test_deployed_app_refuses_to_start_without_a_key(monkeypatch):
    monkeypatch.setenv("RELEASE", "abc")
    monkeypatch.setenv("PLATFORM_API_KEY", "")
    from grok_invoices.entrypoints.http import app

    with pytest.raises(RuntimeError, match="PLATFORM_API_KEY"):
        with TestClient(app):
            pass


def test_without_sample_data_the_platform_holds_only_the_ksef_test_client(monkeypatch):
    monkeypatch.setenv("SAMPLE_DATA", "false")
    from grok_invoices.entrypoints.http import app

    with TestClient(app, headers={"Authorization": "Bearer test-key"}) as client:
        profile = client.get("/api/client").json()
        assert profile["nip"] == "6421983078"
        assert UNKNOWN_CAR not in [vehicle["plate"] for vehicle in profile["fleet"]]
        assert client.get("/api/invoices").json() == []
        assert client.post("/api/ksef/sync", params={"source": "fixtures"}).status_code == 422
        assert client.post("/api/demo/reset").status_code == 204
        assert client.get("/api/invoices").json() == []
