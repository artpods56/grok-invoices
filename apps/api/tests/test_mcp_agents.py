"""The invoice and regulations bots, through their MCP servers. No network."""

import json
from datetime import date

import pytest

from grok_invoices.domain.regulations import CORPUS
from grok_invoices.seed import COMPANY_VAN, UNKNOWN_CAR, _fuel
from grok_invoices.service_layer import services
from grok_invoices.service_layer.commands import AnswerQuestion

INVOICE_URL = "/agents/invoices/mcp"
REGULATIONS_URL = "/agents/regulations/mcp"
INVOICE_TOKEN = "invoice-invite"
REGULATIONS_TOKEN = "regulations-invite"
ACCEPT = "application/json, text/event-stream"

INVOICE_TOOLS = {
    "fetch_new_invoices",
    "add_invoice",
    "list_pending_invoices",
    "get_invoice",
    "search_precedents",
    "list_accounts",
    "post_by_rule",
    "post_by_precedent",
    "escalate",
    "get_timeline",
}
REGULATIONS_TOOLS = {
    "list_open_cases",
    "get_case",
    "get_client_context",
    "search_precedents",
    "list_accounts",
    "search_regulations",
    "list_documents",
    "get_document",
    "ask_client",
    "save_vehicle",
    "decide",
    "get_timeline",
}


@pytest.fixture
def tokens(monkeypatch):
    monkeypatch.setenv("INVOICE_AGENT_TOKEN", INVOICE_TOKEN)
    monkeypatch.setenv("REGULATIONS_AGENT_TOKEN", REGULATIONS_TOKEN)


def _message(response):
    content_type = response.headers.get("content-type", "")
    if "text/event-stream" in content_type:
        data = [line.removeprefix("data:").strip() for line in response.text.splitlines() if line.startswith("data:")]
        assert data, response.text
        return json.loads(data[-1])
    return response.json()


def rpc(client, url, token, method, params=None):
    response = client.post(
        f"{url}?invite={token}",
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
        headers={"accept": ACCEPT},
        follow_redirects=False,
    )
    assert response.status_code == 200, response.text
    assert response.headers.get("location") is None
    assert response.url.path == url
    body = _message(response)
    assert "error" not in body, body
    assert token not in response.text
    return body["result"]


def _text(result) -> str:
    return "\n".join(
        block.get("text", "")
        for block in result.get("content") or []
        if isinstance(block, dict) and block.get("type") == "text"
    )


def call(client, url, token, name, arguments=None):
    result = rpc(client, url, token, "tools/call", {"name": name, "arguments": arguments or {}})
    if result.get("isError") or result.get("is_error"):
        return {"_error": _text(result)}
    data = result.get("structuredContent", result.get("structured_content"))
    if data is None:
        text = _text(result)
        data = json.loads(text) if text else None
    if isinstance(data, dict) and set(data) == {"result"}:
        return data["result"]
    return data


def _property_names(schema, found: set[str]) -> None:
    if not isinstance(schema, dict):
        return
    for key, value in (schema.get("properties") or {}).items():
        found.add(key)
        _property_names(value, found)
    for key in ("items", "$defs", "definitions"):
        child = schema.get(key)
        if isinstance(child, dict):
            for item in child.values() if key != "items" else [child]:
                _property_names(item, found)
    for key in ("anyOf", "oneOf", "allOf"):
        for item in schema.get(key) or []:
            _property_names(item, found)


def test_invite_and_mounted_path(api, tokens, monkeypatch):
    init = {
        "protocolVersion": "2025-11-25",
        "capabilities": {},
        "clientInfo": {"name": "pytest", "version": "0"},
    }
    for url, token in ((INVOICE_URL, INVOICE_TOKEN), (REGULATIONS_URL, REGULATIONS_TOKEN)):
        result = rpc(api, url, token, "initialize", init)
        assert result["protocolVersion"] == "2025-11-25"
        assert "serverInfo" in result

    header = api.post(
        INVOICE_URL,
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        headers={"accept": ACCEPT, "x-invite": INVOICE_TOKEN},
        follow_redirects=False,
    )
    assert header.status_code == 200
    assert header.headers.get("location") is None
    assert header.url.path == INVOICE_URL
    assert INVOICE_TOKEN not in header.text

    secret = "wrong-invite-value"
    for url, token in (
        (INVOICE_URL, None),
        (INVOICE_URL, secret),
        (INVOICE_URL, REGULATIONS_TOKEN),
        (REGULATIONS_URL, INVOICE_TOKEN),
        (REGULATIONS_URL, ""),
    ):
        target = url if token is None else f"{url}?invite={token}"
        response = api.post(
            target,
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": init},
            headers={"accept": ACCEPT},
            follow_redirects=False,
        )
        assert response.status_code == 401, (target, response.status_code, response.text)
        assert response.json()["detail"] == "Missing or invalid invite"
        assert response.headers.get("location") is None
        if token:
            assert token not in response.text

    monkeypatch.delenv("INVOICE_AGENT_TOKEN")
    monkeypatch.delenv("REGULATIONS_AGENT_TOKEN")
    refused = api.post(
        f"{INVOICE_URL}?invite={INVOICE_TOKEN}",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        headers={"accept": ACCEPT},
        follow_redirects=False,
    )
    assert refused.status_code == 401
    assert INVOICE_TOKEN not in refused.text


def test_each_server_lists_only_its_tools(api, tokens):
    invoice_tools = rpc(api, INVOICE_URL, INVOICE_TOKEN, "tools/list")["tools"]
    regulations_tools = rpc(api, REGULATIONS_URL, REGULATIONS_TOKEN, "tools/list")["tools"]
    assert {tool["name"] for tool in invoice_tools} == INVOICE_TOOLS
    assert {tool["name"] for tool in regulations_tools} == REGULATIONS_TOOLS

    for tool in (*invoice_tools, *regulations_tools):
        names: set[str] = set()
        _property_names(tool.get("inputSchema") or tool.get("input_schema") or {}, names)
        assert "actor" not in names, tool["name"]
        assert "source" not in names, tool["name"]

    description = next(tool["description"] for tool in invoice_tools if tool["name"] == "search_precedents")
    assert "Looking similar is not enough" in description
    assert "only applicable counts" in description


def test_demo_through_the_tools(api, tokens):
    services.sync_ksef("fixtures")
    pending = call(api, INVOICE_URL, INVOICE_TOKEN, "list_pending_invoices")
    by_plate = {invoice["vehicle_plate"]: invoice for invoice in pending}
    it, fuel, unknown = by_plate[None], by_plate[COMPANY_VAN], by_plate[UNKNOWN_CAR]

    assert call(api, INVOICE_URL, INVOICE_TOKEN, "search_precedents", {"invoice_id": it["id"]}) == []
    posted = call(api, INVOICE_URL, INVOICE_TOKEN, "post_by_rule", {
        "invoice_id": it["id"],
        "account": "402",
        "vat_deduction_percent": 100,
        "rationale": "Abonament za utrzymanie systemu IT",
        "confidence": 0.95,
    })
    assert (posted["actor"], posted["source"], posted["account"]) == ("invoice_agent", "rule", "402")

    match = call(api, INVOICE_URL, INVOICE_TOKEN, "search_precedents", {"invoice_id": fuel["id"]})[0]
    assert match["applicable"] is True
    precedent_id = match["precedent"]["id"]
    rationale = f"Zastosowano wcześniejsze księgowanie #{precedent_id}, ponieważ ten sam użytek mieszany floty."
    reused = call(api, INVOICE_URL, INVOICE_TOKEN, "post_by_precedent", {
        "invoice_id": fuel["id"],
        "precedent_id": precedent_id,
        "rationale": rationale,
        "confidence": 0.9,
    })
    assert reused["precedent_id"] == precedent_id
    assert reused["account"] == match["precedent"]["account"]
    assert reused["vat_deduction_percent"] == match["precedent"]["vat_deduction_percent"]
    assert rationale in reused["rationale"]

    unknown_match = call(api, INVOICE_URL, INVOICE_TOKEN, "search_precedents", {"invoice_id": unknown["id"]})[0]
    assert unknown_match["applicable"] is False
    assert UNKNOWN_CAR in unknown_match["blockers"][0]
    refused = call(api, INVOICE_URL, INVOICE_TOKEN, "post_by_precedent", {
        "invoice_id": unknown["id"],
        "precedent_id": precedent_id,
        "rationale": "Jak w precedensie",
        "confidence": 0.5,
    })
    assert "does not apply" in refused["_error"]

    detail = call(api, INVOICE_URL, INVOICE_TOKEN, "get_invoice", {"invoice_id": unknown["id"]})
    rendered = json.dumps(detail)
    assert "<?xml" not in rendered and "source_xml" not in rendered and "document" not in detail
    assert detail["vehicle_plate"] == UNKNOWN_CAR
    assert detail["lines"][0]["vat_rate"] == "23"
    assert UNKNOWN_CAR in detail["lines"][0]["name"]

    case = call(api, INVOICE_URL, INVOICE_TOKEN, "escalate", {
        "invoice_id": unknown["id"],
        "reason": "; ".join(unknown_match["blockers"]),
    })
    assert case["opened_by"] == "invoice_agent"
    assert case["invoice"]["vehicle_plate"] == UNKNOWN_CAR

    open_cases = call(api, REGULATIONS_URL, REGULATIONS_TOKEN, "list_open_cases")
    listed = next(item for item in open_cases if item["id"] == case["id"])
    assert listed["invoice"]["id"] == unknown["id"]
    assert listed["questions"] == []

    question = call(api, REGULATIONS_URL, REGULATIONS_TOKEN, "ask_client", {
        "case_id": case["id"],
        "question": "Widzę paliwo na GD 9R247. Tej rejestracji nie ma we flocie. Które to auto i czy jest firmowe, czy prywatne?",
    })
    assert question["asked_by"] == "regulations_agent"

    early = call(api, REGULATIONS_URL, REGULATIONS_TOKEN, "decide", {
        "case_id": case["id"],
        "account": "403",
        "vat_deduction_percent": 50,
        "rationale": "Za wcześnie",
        "confidence": 0.4,
        "legal_basis": "art. 86a ust. 1 ustawy o VAT",
        "conditions": {"vehicle_usage": "mixed", "vehicle_plate": UNKNOWN_CAR},
    })
    assert "waiting for the client" in early["_error"]

    services.answer_question(question["id"], AnswerQuestion(
        answer="Firmowe, Skoda Octavia, użytek mieszany",
    ))

    fleet = call(api, REGULATIONS_URL, REGULATIONS_TOKEN, "save_vehicle", {
        "plate": UNKNOWN_CAR, "model": "Skoda Octavia", "usage": "mixed",
    })
    assert any(vehicle["plate"] == UNKNOWN_CAR for vehicle in fleet["fleet"])
    assert "phone" not in fleet

    found = call(api, REGULATIONS_URL, REGULATIONS_TOKEN, "search_regulations", {"query": "paliwo użytek mieszany"})
    assert "23%" in found["booking_note"]
    citations = {item["citation"] for item in found["provisions"]}
    assert citations
    assert citations <= {item.citation for item in CORPUS}
    assert "art. 86a ust. 1 ustawy o VAT" in citations

    decision = call(api, REGULATIONS_URL, REGULATIONS_TOKEN, "decide", {
        "case_id": case["id"],
        "account": "403",
        "vat_deduction_percent": 50,
        "rationale": "Paliwo do firmowej Skody w użytku mieszanym, art. 86a ust. 1.",
        "confidence": 0.9,
        "legal_basis": "art. 86a ust. 1 ustawy o VAT",
        "conditions": {"vehicle_usage": "mixed", "vehicle_plate": UNKNOWN_CAR},
    })
    assert (decision["actor"], decision["source"], decision["reusable"]) == ("regulations_agent", "regulation", True)
    new_precedent = decision["id"]

    later_xml = _fuel("ON/2026/11/106", date(2026, 11, 6), UNKNOWN_CAR, "30").decode()
    added = call(api, INVOICE_URL, INVOICE_TOKEN, "add_invoice", {
        "ksef_number": "1132511471-20261106-DEMO-000005",
        "xml": later_xml,
    })
    assert added["stored"] is True
    assert "<?xml" not in json.dumps(added)
    again = call(api, INVOICE_URL, INVOICE_TOKEN, "add_invoice", {
        "ksef_number": "1132511471-20261106-DEMO-000005",
        "xml": later_xml,
    })
    assert again == {"stored": False, "detail": "Invoice was already stored"}

    later_id = added["invoice"]["id"]
    later_match = next(
        item for item in call(api, INVOICE_URL, INVOICE_TOKEN, "search_precedents", {"invoice_id": later_id})
        if item["precedent"]["id"] == new_precedent
    )
    assert later_match["applicable"] is True
    booked = call(api, INVOICE_URL, INVOICE_TOKEN, "post_by_precedent", {
        "invoice_id": later_id,
        "precedent_id": new_precedent,
        "rationale": f"Zastosowano wcześniejsze księgowanie #{new_precedent}, ponieważ ta sama Skoda w użytku mieszanym.",
        "confidence": 0.92,
    })
    assert booked["precedent_id"] == new_precedent
    assert booked["source"] == "precedent"

    timeline = call(api, REGULATIONS_URL, REGULATIONS_TOKEN, "get_timeline", {"after_event_id": 0})
    assert {"invoice_posted", "case_opened", "question_asked", "precedent_created"} <= {event["type"] for event in timeline}


def test_regulations_bot_reads_what_the_client_submitted(api, tokens):
    from grok_invoices.service_layer import services

    document = services.submit_document("Umowa leasingu", "Skoda GD 9R247, leasing do 2028")
    listed = call(api, REGULATIONS_URL, REGULATIONS_TOKEN, "list_documents")
    assert "Umowa leasingu" in str(listed)
    assert "leasing do 2028" not in str(listed)
    opened = call(api, REGULATIONS_URL, REGULATIONS_TOKEN, "get_document", {"document_id": document.id})
    assert "leasing do 2028" in str(opened)
