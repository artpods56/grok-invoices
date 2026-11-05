"""The client agent's MCP server, over stateless JSON-RPC on /agents/client/mcp."""

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from cryptography.fernet import Fernet

from grok_invoices.ksef import DEMO_SELLER_NAME, fetch_new
from grok_invoices.seed import UNKNOWN_CAR
from grok_invoices.service_layer import commands, services
from grok_invoices.service_layer.unit_of_work import UnitOfWork
from grok_invoices.settings import get_settings

INVITE = "invite-9f3e-not-stored"
TOKEN = "vault!ksef-token-do-not-leak-91qx"
DOCUMENT = "umowa-prywatna-nie-do-api"
MCP_PATH = "/agents/client/mcp"
ACCEPT = "application/json, text/event-stream"
TOOLS = {
    "start_onboarding",
    "configure_ksef",
    "submit_document",
    "list_open_questions",
    "answer_question",
    "get_status",
}


def _key() -> str:
    return Fernet.generate_key().decode()


@pytest.fixture
def invite(monkeypatch):
    monkeypatch.setenv("CLIENT_INVITE_TOKEN", INVITE)
    monkeypatch.setenv("SECRET_ENCRYPTION_KEY", _key())


def rpc(api, method, params=None, *, invite=INVITE, headers=None):
    """POST one JSON-RPC call. Redirects stay visible: a 307 would drop or leak ?invite=."""
    extra = {"accept": ACCEPT, "content-type": "application/json"}
    if headers:
        extra.update(headers)
    response = api.post(
        MCP_PATH,
        params={} if invite is None else {"invite": invite},
        headers=extra,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
        follow_redirects=False,
    )
    assert response.status_code not in (301, 302, 303, 307, 308)
    assert response.history == []
    assert "location" not in response.headers
    assert response.request.url.path == MCP_PATH
    return response


def payload(response):
    body = response.json()
    assert response.status_code == 200, body
    assert "error" not in body, body
    result = body["result"]
    assert result.get("isError") is not True, result
    structured = result.get("structuredContent")
    if isinstance(structured, dict) and set(structured) == {"result"}:
        return structured["result"]
    if isinstance(structured, dict):
        return structured
    return json.loads(result["content"][0]["text"])


def tool_error(response) -> str:
    body = response.json()
    assert response.status_code == 200, body
    result = body["result"]
    assert result["isError"] is True
    return result["content"][0]["text"]


def call(api, name, arguments=None):
    return rpc(api, "tools/call", {"name": name, "arguments": arguments or {}})


def store_bytes(tmp_path) -> bytes:
    blob = b""
    for path in tmp_path.iterdir():
        if path.is_file():
            blob += path.read_bytes()
    return blob


def test_a_missing_or_wrong_invite_is_refused_and_the_path_does_not_redirect(api, monkeypatch):
    monkeypatch.delenv("CLIENT_INVITE_TOKEN", raising=False)
    real = get_settings

    def unset_invite():
        return real().model_copy(update={"client_invite_token": None})

    monkeypatch.setattr("grok_invoices.entrypoints.mcp.get_settings", unset_invite)
    refused = rpc(api, "initialize", _initialize(), invite=INVITE)
    assert refused.status_code == 401
    assert refused.json() == {"detail": "Missing or invalid invite"}
    assert INVITE not in refused.text

    monkeypatch.setattr("grok_invoices.entrypoints.mcp.get_settings", real)
    monkeypatch.setenv("CLIENT_INVITE_TOKEN", INVITE)
    for response in (
        rpc(api, "tools/list", invite=None),
        rpc(api, "tools/list", invite="wrong-invite"),
        rpc(api, "tools/list", invite=None, headers={"x-invite": "wrong-invite"}),
    ):
        assert response.status_code == 401
        assert response.json()["detail"] == "Missing or invalid invite"
        assert INVITE not in response.text

    # The platform API key is already on the client. It does not authorize MCP.
    assert "authorization" in {name.lower() for name in api.headers}
    listed = rpc(api, "tools/list")
    assert listed.status_code == 200
    by_header = rpc(api, "tools/list", invite=None, headers={"x-invite": INVITE})
    assert by_header.status_code == 200
    assert api.post("/mcp", headers={"accept": ACCEPT}, json={}).status_code == 404


def test_initialize_lists_only_the_client_tools(api, invite):
    started = rpc(api, "initialize", _initialize())
    assert started.status_code == 200
    result = started.json()["result"]
    assert result["protocolVersion"] == "2025-06-18"
    assert result["serverInfo"]["name"] == "grok-invoices-client"

    tools = rpc(api, "tools/list").json()["result"]["tools"]
    assert {tool["name"] for tool in tools} == TOOLS
    configure = next(tool for tool in tools if tool["name"] == "configure_ksef")
    assert "vault" in configure["description"]
    assert "never from chat" in configure["description"]
    assert payload(call(api, "get_status"))["onboarded"] is False


def test_each_tool_and_a_client_answer_round_trip(api, invite, tmp_path):
    company = payload(call(api, "start_onboarding", {"nip": "526-104-08-28", "company_name": "Transpol sp. z o.o."}))
    assert company["nip"] == "5261040828"
    assert company["name"] == "Transpol sp. z o.o."
    assert "phone" not in company

    configured = payload(call(api, "configure_ksef", {"ksef_token": f"  {TOKEN}  "}))
    assert configured == {"configured": True, "last_four": TOKEN[-4:]}
    status = payload(call(api, "get_status"))
    assert status["onboarded"] is True
    assert status["ksef_token_configured"] is True
    assert status["ksef_token_last_four"] == TOKEN[-4:]
    assert TOKEN not in json.dumps(status)

    stored = payload(call(api, "submit_document", {"name": "Umowa", "content_text": DOCUMENT}))
    assert stored == {"id": stored["id"], "name": "Umowa"}
    assert DOCUMENT not in json.dumps(stored)
    assert payload(call(api, "list_open_questions")) == {"questions": []}

    invoices = services.sync_ksef("fixtures")
    unknown = next(invoice for invoice in invoices if invoice.vehicle_plate == UNKNOWN_CAR)
    case = services.escalate_invoice(unknown.id, commands.Escalate(reason="Auto spoza floty"))
    question = services.ask_client(case.id, commands.AskClient(text="Do którego auta był ten zakup?"))

    open_questions = payload(call(api, "list_open_questions"))["questions"]
    assert len(open_questions) == 1
    asked = open_questions[0]
    assert asked["id"] == question.id
    assert asked["vehicle_plate"] == UNKNOWN_CAR
    assert asked["seller_name"] == DEMO_SELLER_NAME
    assert asked["gross"] == "246.00"
    assert asked["ksef_number"] == unknown.ksef_number

    answer = "Auto GD 9R247, jazda firmowa"
    answered = payload(call(api, "answer_question", {"question_id": question.id, "answer": answer}))
    assert answered["status"] == "answered"
    assert answered["answered_by"] == "client_agent"
    assert answered["answer"] == answer
    assert services.get_case(case.id).status == "open"
    assert payload(call(api, "get_status"))["open_questions"] == 0

    events = [event.model_dump(mode="json") for event in services.list_events()]
    by_type = {event["type"]: event for event in events}
    assert by_type["onboarding_started"]["summary"] == "Rejestracja klienta: Transpol sp. z o.o., NIP 5261040828"
    assert by_type["ksef_token_configured"]["summary"] == "Skonfigurowano token KSeF"
    assert by_type["ksef_token_configured"]["data"] == {}
    assert by_type["document_submitted"]["summary"] == "Dokument od klienta: Umowa"
    assert by_type["question_answered"]["actor"] == "client_agent"
    event_blob = json.dumps(events)
    assert TOKEN not in event_blob
    assert TOKEN[-4:] not in json.dumps(by_type["ksef_token_configured"])
    assert DOCUMENT not in event_blob

    blob = store_bytes(tmp_path)
    assert TOKEN.encode() not in blob
    assert DOCUMENT.encode() in blob
    with UnitOfWork(write=False) as uow:
        ciphertext = uow.ksef_tokens.all()[-1].ciphertext
    assert TOKEN not in ciphertext
    assert services.decrypt_secret(ciphertext) == TOKEN

    for path, methods in api.get("/openapi.json").json()["paths"].items():
        if "get" not in methods or "{" in path:
            continue
        body = api.get(path).text
        assert TOKEN not in body
        assert DOCUMENT not in body
        assert INVITE not in body


def test_a_bad_nip_is_a_tool_error_the_bot_can_read(api, invite):
    message = tool_error(call(api, "start_onboarding", {"nip": "1234567890", "company_name": "Zła firma"}))
    assert message == "NIP checksum is invalid"
    assert services.get_client().nip != "1234567890"


def test_configure_ksef_refuses_when_encryption_is_not_configured(api, monkeypatch):
    monkeypatch.setenv("CLIENT_INVITE_TOKEN", INVITE)
    monkeypatch.setenv("SECRET_ENCRYPTION_KEY", "")
    message = tool_error(call(api, "configure_ksef", {"ksef_token": TOKEN}))
    assert message == "Secret encryption is not configured"


def test_a_stored_token_is_decrypted_outside_the_transaction_and_used_to_log_in(api, invite, monkeypatch):
    services.configure_ksef(TOKEN)
    depth = {"n": 0}
    real_enter = UnitOfWork.__enter__
    real_exit = UnitOfWork.__exit__

    def enter(self):
        depth["n"] += 1
        return real_enter(self)

    def leave(self, exc_type, exc, tb):
        try:
            return real_exit(self, exc_type, exc, tb)
        finally:
            depth["n"] -= 1

    seen = {}

    def fake_fetch(nip, since, known, *, ksef_token=None):
        seen["depth"] = depth["n"]
        seen["token"] = ksef_token
        seen["nip"] = nip
        return []

    monkeypatch.setattr(UnitOfWork, "__enter__", enter)
    monkeypatch.setattr(UnitOfWork, "__exit__", leave)
    monkeypatch.setattr("grok_invoices.service_layer.services.ksef.fetch_new", fake_fetch)
    assert services.sync_ksef("fixtures")
    assert "token" not in seen
    assert services.sync_ksef("test") == []
    assert seen == {"depth": 0, "token": TOKEN, "nip": "8943210057"}


def test_fetch_new_uses_the_token_when_one_was_stored(monkeypatch):
    client = MagicMock()
    client.__enter__.return_value = client
    client.authentication.with_token.return_value.invoices.search.return_value = []
    client.authentication.with_test_certificate.return_value.invoices.search.return_value = []
    monkeypatch.setattr("grok_invoices.ksef.Client", MagicMock(return_value=client))
    since = datetime(2026, 11, 1, tzinfo=UTC)

    assert fetch_new("8943210057", since, set(), ksef_token=TOKEN) == []
    client.authentication.with_token.assert_called_once_with(ksef_token=TOKEN, nip="8943210057")

    assert fetch_new("8943210057", since, set()) == []
    client.authentication.with_test_certificate.assert_called_once_with(nip="8943210057")


def test_the_invite_is_redacted_in_access_logs(caplog):
    import logging

    from grok_invoices.entrypoints.mcp import redact_invite_from_logs

    redact_invite_from_logs()
    logger = logging.getLogger("uvicorn.access")
    logger.setLevel(logging.INFO)
    with caplog.at_level(logging.INFO, logger="uvicorn.access"):
        logger.info('%s - "%s %s HTTP/%s" %d', "127.0.0.1", "POST", f"{MCP_PATH}?invite={INVITE}", "1.1", 200)
        logger.info("POST %s?invite=%s", MCP_PATH, INVITE)
    assert INVITE not in caplog.text
    assert caplog.text.count("invite=[redacted]") == 2


def _initialize():
    return {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "0.1.0"},
    }
