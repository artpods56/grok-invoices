import pytest
from fastapi.testclient import TestClient

from apps.api.src.seed import COMPANY_VAN, UNKNOWN_CAR

KEY = "test-key"
AUTH = {"Authorization": f"Bearer {KEY}"}


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PLATFORM_API_KEY", KEY)
    monkeypatch.delenv("RELEASE", raising=False)
    monkeypatch.setenv("AGENT_MODE", "demo")
    monkeypatch.delenv("MCP_INVITE_TOKEN", raising=False)
    from main import create_app

    with TestClient(create_app(), headers=AUTH) as client:
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
    api.put("/api/client/vehicles", json={"plate": UNKNOWN_CAR.lower(), "model": "Skoda Octavia", "usage": "mixed"})
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
    from main import create_app

    with pytest.raises(RuntimeError, match="PLATFORM_API_KEY"):
        with TestClient(create_app()):
            pass


def run_agent(api, invoice_id=None, mode="demo"):
    return api.post("/api/agents/run", json={"mode": mode, "invoice_id": invoice_id})


def vehicle_reply(**changes):
    return {"vehicle_plate": UNKNOWN_CAR, "usage": "mixed", "business_purpose": "Travel to a client site", **changes}


def test_agents_complete_the_demo_and_reuse_context_without_another_question(api):
    it, fuel, unknown = synced(api)
    response = run_agent(api)
    assert response.status_code == 200
    results = response.json()
    assert [r["status"] for r in results] == ["completed", "completed", "waiting_for_client"]
    assert all(r["simulation"] for r in results)
    assert results[1]["invoice"]["postings"][0]["source"] == "precedent"
    question = api.get("/api/questions", params={"status": "open"}).json()[0]
    partial = api.post(f"/api/agents/questions/{question['id']}/answer", json={"usage": "mixed"})
    assert partial.json()["status"] == "waiting_for_client"
    assert "vehicle_plate" in partial.json()["missing"]
    assert api.get(f"/api/cases/{question['case_id']}").json()["questions"][0]["status"] == "open"
    completed = api.post(f"/api/agents/questions/{question['id']}/answer", json=vehicle_reply())
    assert completed.status_code == 200
    posting = completed.json()["invoice"]["postings"][0]
    assert completed.json()["status"] == "completed"
    assert posting["deductible_vat"] == "23.00"
    assert posting["conditions"]["vehicle_plate"] == UNKNOWN_CAR
    assert posting["legal_basis"] and posting["conditions"]["policy_version"]
    before = api.get("/api/events").json()
    assert api.post(f"/api/agents/questions/{question['id']}/answer", json=vehicle_reply()).status_code == 200
    assert run_agent(api, unknown["id"]).json()[0]["status"] == "completed"
    assert api.get("/api/events").json() == before
    assert api.post(f"/api/agents/questions/{question['id']}/answer", json=vehicle_reply(usage="company")).status_code == 409

    follow_up = {k: v for k, v in unknown.items() if k not in ("id", "received_at", "status")}
    follow_up["ksef_number"] += "-FOLLOWUP"
    new_id = api.post("/api/invoices", json=follow_up).json()["id"]
    reused = run_agent(api, new_id).json()[0]
    assert reused["status"] == "completed"
    assert reused["invoice"]["postings"][0]["precedent_id"] == posting["id"]
    assert api.get("/api/questions", params={"status": "open"}).json() == []


def test_agents_reject_a_vehicle_answer_for_another_case(api):
    unknown = synced(api)[2]
    run_agent(api, unknown["id"])
    question = api.get("/api/questions").json()[0]
    result = api.post(f"/api/agents/questions/{question['id']}/answer", json=vehicle_reply(vehicle_plate=COMPANY_VAN))
    assert result.status_code == 409
    assert api.get("/api/questions").json()[0]["status"] == "open"
    assert len(api.get("/api/client").json()["fleet"]) == 1


def test_exclusive_use_does_not_automatically_authorize_full_vat(api):
    unknown = synced(api)[2]
    run_agent(api, unknown["id"])
    question = api.get("/api/questions").json()[0]
    result = api.post(f"/api/agents/questions/{question['id']}/answer", json=vehicle_reply(usage="company"))
    assert result.json()["status"] == "blocked"
    assert result.json()["invoice"]["postings"] == []


def test_missing_xai_configuration_blocks_without_demo_fallback(api, monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    it = synced(api)[0]
    result = run_agent(api, it["id"], "xai").json()[0]
    assert result["status"] == "blocked"
    assert result["mode"] == "xai"
    assert result["invoice"]["postings"] == []
    assert run_agent(api, it["id"], "demo").json()[0]["status"] == "completed"


def test_provider_context_race_prevents_a_stale_decision(api, monkeypatch):
    from apps.api.src import agents
    from apps.api.src.schemas import AgentProposal

    it = synced(api)[0]

    def changed(context, mode):
        api.post("/api/client/facts", json={"key": "new_context", "value": "Needs reassessment"})
        return AgentProposal(category="it_services", action="analyse", rationale="Fixture classification")

    monkeypatch.setattr(agents, "propose", changed)
    assert run_agent(api, it["id"]).status_code == 409
    assert api.get(f"/api/invoices/{it['id']}").json()["postings"] == []


def test_precedent_treatment_cannot_be_changed_and_policy_changes_invalidate_it(api):
    import json
    _, fuel, _ = synced(api)
    match = api.get(f"/api/invoices/{fuel['id']}/precedents").json()[0]
    assert post(api, fuel["id"], account="403", vat_deduction_percent=100, source="precedent",
                precedent_id=match["precedent"]["id"]).status_code == 409
    api.post("/api/client/facts", json={"key": "agent_policy", "value": json.dumps({"version": "new-policy"})})
    assert api.get(f"/api/invoices/{fuel['id']}/precedents").json()[0]["applicable"] is False
    assert run_agent(api, fuel["id"]).json()[0]["status"] == "blocked"


def test_agent_does_not_claim_a_missing_policy_or_non_demo_document_is_supported(api):
    it = synced(api)[0]
    api.post("/api/client/facts", json={"key": "agent_policy", "value": "invalid"})
    assert run_agent(api, it["id"]).json()[0]["status"] == "blocked"
    assert api.post("/api/agents/setup-demo").status_code == 200
    assert run_agent(api, it["id"]).json()[0]["status"] == "completed"
    body = {k: v for k, v in it.items() if k not in ("id", "received_at", "status")}
    body["ksef_number"] = "real-document-not-supported"
    new_id = api.post("/api/invoices", json=body).json()["id"]
    assert run_agent(api, new_id).json()[0]["status"] == "blocked"


def mcp_request(api, method, params=None, headers=None):
    return api.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
                    headers={"Accept": "application/json, text/event-stream", **(headers or {})})


def mcp_tool(api, name, arguments=None):
    import json
    response = mcp_request(api, "tools/call", {"name": name, "arguments": arguments or {}})
    assert response.status_code == 200, response.text
    result = response.json()["result"]
    assert not result.get("isError"), result
    return result.get("structuredContent") or json.loads(result["content"][0]["text"])


def test_mcp_transport_initializes_lists_six_tools_and_requires_connection_auth(api, monkeypatch):
    init = mcp_request(api, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                           "clientInfo": {"name": "test", "version": "1"}})
    assert init.status_code == 200
    assert init.json()["result"]["serverInfo"]["name"] == "Grok Invoices"
    tools = mcp_request(api, "tools/list").json()["result"]["tools"]
    assert {t["name"] for t in tools} == {
        "start_onboarding", "configure_ksef", "submit_document", "list_open_questions", "answer_question", "get_status",
    }
    assert mcp_request(api, "tools/list", headers={"Authorization": ""}).status_code == 401
    monkeypatch.setenv("MCP_INVITE_TOKEN", "demo-invitation")
    assert mcp_request(api, "tools/list", headers={"Authorization": "Bearer demo-invitation"}).status_code == 200
    assert api.post("/api/agents/run", json={}, headers={"Authorization": "Bearer demo-invitation"}).status_code == 401


def test_mcp_documents_answers_and_status_share_platform_state(api):
    from apps.api.src.seed import KSEF_INBOX
    unknown = KSEF_INBOX[2].model_dump(mode="json")
    first = mcp_tool(api, "submit_document", {"invoice": unknown})
    assert first["status"] == "waiting_for_client"
    assert mcp_tool(api, "submit_document", {"invoice": unknown})["invoice_id"] == first["invoice_id"]
    assert len(api.get("/api/invoices").json()) == 2
    altered = {**unknown, "description": "Conflicting duplicate"}
    refused = mcp_request(api, "tools/call", {"name": "submit_document", "arguments": {"invoice": altered}})
    assert refused.json()["result"]["isError"] is True
    status = mcp_tool(api, "get_status")
    question = status["open_questions"][0]
    result = mcp_tool(api, "answer_question", {"question_id": question["id"], "answer": vehicle_reply()})
    assert result["status"] == "completed"
    assert api.get(f"/api/invoices/{first['invoice_id']}").json()["status"] == "posted"
    assert mcp_tool(api, "configure_ksef")["accepts_credentials"] is False
    assert mcp_tool(api, "start_onboarding")["single_company_demo"] is True


def test_setup_does_not_rebuild_existing_data(api):
    invoices = synced(api)
    assert api.post("/api/agents/setup-demo").status_code == 200
    assert api.get("/api/invoices").json()[1:] == invoices


def test_accountant_takeover_is_respected_by_the_agent_runner(api):
    it = synced(api)[0]
    case = api.post(f"/api/invoices/{it['id']}/escalate", json={"reason": "Manual review"}).json()
    api.post(f"/api/cases/{case['id']}/take-over")
    assert run_agent(api, it["id"]).json()[0]["status"] == "blocked"
    assert api.get(f"/api/invoices/{it['id']}").json()["postings"] == []


def test_xai_role_proposals_are_schema_checked_and_do_not_select_tax_rates(api, monkeypatch):
    import httpx
    from apps.api.src import agents

    unknown = synced(api)[2]
    calls = []

    def respond(request):
        import json
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({
            "category": "vehicle_fuel", "action": "analyse", "rationale": "Vehicle context needs review",
        })}}]})

    original_client = httpx.Client
    monkeypatch.setenv("XAI_API_KEY", "fake-provider-test-key")
    monkeypatch.setattr(agents.httpx, "Client", lambda **kwargs: original_client(transport=httpx.MockTransport(respond), **kwargs))
    result = run_agent(api, unknown["id"], "xai").json()[0]
    assert result["status"] == "waiting_for_client"
    assert len(calls) == 2
    assert "invoice triage agent" in calls[0]["messages"][0]["content"]
    assert "regulatory agent" in calls[1]["messages"][0]["content"]
    assert "vat_deduction_percent" not in calls[0]["response_format"]["json_schema"]["schema"]["properties"]
    assert "fake-provider-test-key" not in str(api.get("/api/events").json())


def test_invalid_model_output_cannot_become_a_posting(api, monkeypatch):
    import httpx
    from apps.api.src import agents

    it = synced(api)[0]
    original_client = httpx.Client
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"choices": [{"message": {"content": "not-json"}}]}))
    monkeypatch.setenv("XAI_API_KEY", "fake-provider-test-key")
    monkeypatch.setattr(agents.httpx, "Client", lambda **kwargs: original_client(transport=transport, **kwargs))
    result = run_agent(api, it["id"], "xai").json()[0]
    assert result["status"] == "blocked"
    assert result["invoice"]["postings"] == []


def test_unsupported_precedent_conditions_fail_closed(api):
    it, _, _ = synced(api)
    created = post(api, it["id"], reusable=True, conditions={"unverified_fact": {"value": True}}).json()
    body = {k: v for k, v in it.items() if k not in ("id", "received_at", "status")}
    body["ksef_number"] += "-COPY"
    invoice_id = api.post("/api/invoices", json=body).json()["id"]
    matches = api.get(f"/api/invoices/{invoice_id}/precedents").json()
    assert matches[0]["applicable"] is False
    assert post(api, invoice_id, source="precedent", precedent_id=created["id"]).status_code == 409
