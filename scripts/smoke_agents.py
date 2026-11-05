"""Exercise all three real MCP transports against an isolated local demo platform.

Run: uv run python -m scripts.smoke_agents
Uses synthetic fixtures, a temporary DB and an ephemeral loopback port. No model,
Grok Bot, ELI, KSeF or production requests. Never resets an existing database.
"""

import asyncio
import json
import os
import secrets
import socket
import tempfile
import threading
import time
from contextlib import AsyncExitStack
from datetime import date

import httpx
import uvicorn
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


def tool_data(result):
    assert not result.is_error, "MCP tool returned an error"
    data = result.structured_content
    if data is None:
        data = json.loads(result.content[0].text)
    if isinstance(data, dict) and set(data) == {"result"}:
        return data["result"]
    return data


async def connect(stack, base_url, role, token):
    http = await stack.enter_async_context(httpx.AsyncClient(
        headers={"X-Invite": token}, timeout=30, trust_env=False,
    ))
    receive, send = await stack.enter_async_context(
        streamable_http_client(f"{base_url}/agents/{role}/mcp", http_client=http)
    )
    session = await stack.enter_async_context(ClientSession(receive, send))
    await session.initialize()
    return session


async def exercise(url, key, tokens):
    from grok_invoices.seed import COMPANY_VAN, UNKNOWN_CAR, _fuel

    async with httpx.AsyncClient(headers={"Authorization": f"Bearer {key}"}, timeout=30, trust_env=False) as http:
        synced = await http.post(f"{url}/api/ksef/sync")
        synced.raise_for_status()
    async with AsyncExitStack() as stack:
        invoice = await connect(stack, url, "invoices", tokens["INVOICE_AGENT_TOKEN"])
        regulatory = await connect(stack, url, "regulations", tokens["REGULATIONS_AGENT_TOKEN"])
        client = await connect(stack, url, "client", tokens["CLIENT_INVITE_TOKEN"])

        async def call(session, name, **kwargs):
            return tool_data(await session.call_tool(name, kwargs))

        tool_counts = {
            role: len((await session.list_tools()).tools)
            for role, session in (("invoices", invoice), ("regulations", regulatory), ("client", client))
        }
        assert tool_counts == {"invoices": 10, "regulations": 16, "client": 6}
        pending = await call(invoice, "list_pending_invoices")
        by_plate = {item["vehicle_plate"]: item for item in pending}
        await call(invoice, "post_by_rule", invoice_id=by_plate[None]["id"], account="402",
                   vat_deduction_percent=100, rationale="SYNTHETIC DEMO IT policy", confidence=0.95)
        known = by_plate[COMPANY_VAN]["id"]
        match = (await call(invoice, "search_precedents", invoice_id=known))[0]
        assert match["applicable"] is True
        await call(invoice, "post_by_precedent", invoice_id=known, precedent_id=match["precedent"]["id"],
                   rationale="SYNTHETIC DEMO: matched fleet vehicle and mixed use", confidence=0.9)
        unknown = by_plate[UNKNOWN_CAR]["id"]
        match = (await call(invoice, "search_precedents", invoice_id=unknown))[0]
        assert match["applicable"] is False
        case = await call(invoice, "escalate", invoice_id=unknown, reason="Unknown vehicle and business purpose")
        question = await call(regulatory, "ask_client", case_id=case["id"],
                              question=f"Which car is {UNKNOWN_CAR}, how is it used and what was the purchase purpose?")
        open_questions = await call(client, "list_open_questions")
        assert question["id"] in [item["id"] for item in open_questions["questions"]]
        reply = {"question_id": question["id"], "answer": "Skoda Octavia, mixed use, business travel"}
        first = await call(client, "answer_question", **reply)
        replay = await call(client, "answer_question", **reply)
        assert first == replay
        reopened = await call(regulatory, "get_case", case_id=case["id"])
        assert reopened["status"] == "open"
        await call(regulatory, "save_vehicle", plate=UNKNOWN_CAR, model="Skoda Octavia", usage="mixed")
        examples = await call(regulatory, "search_regulations", query="fuel mixed")
        assert examples["authoritative"] is False
        posting = await call(regulatory, "decide", case_id=case["id"], account="403", vat_deduction_percent=50,
                             rationale="SYNTHETIC DEMO: confirmed mixed use and business travel", confidence=0.9,
                             legal_basis="SYNTHETIC DEMO: illustrative VAT Act Article 86a(1), not live legal validation",
                             conditions={"vehicle_plate": UNKNOWN_CAR, "vehicle_usage": "mixed"})
        assert posting["deductible_vat"] == "23.00"
        later = await call(invoice, "add_invoice", ksef_number="1132511471-20261106-DEMO-000005",
                           xml=_fuel("ON/2026/11/106", date(2026, 11, 6), UNKNOWN_CAR, "30").decode())
        later_match = next(item for item in await call(invoice, "search_precedents", invoice_id=later["invoice"]["id"])
                           if item["precedent"]["id"] == posting["id"])
        assert later_match["applicable"] is True
        await call(invoice, "post_by_precedent", invoice_id=later["invoice"]["id"], precedent_id=posting["id"],
                   rationale="SYNTHETIC DEMO: same confirmed vehicle and usage", confidence=0.9)
        assert (await call(client, "list_open_questions"))["questions"] == []
        status = await call(client, "get_status")
        print(json.dumps({"transport": "real localhost MCP", "tool_counts": tool_counts,
                          "synthetic_demo": True, "duplicate_answer": "idempotent",
                          "later_precedent": "reused", "status": status}))


def main():
    with tempfile.TemporaryDirectory(prefix="grok-agent-smoke-") as directory:
        os.environ["DATA_DIR"] = directory
        os.environ["PLATFORM_API_KEY"] = key = secrets.token_urlsafe(24)
        tokens = {name: secrets.token_urlsafe(24) for name in
                  ("INVOICE_AGENT_TOKEN", "REGULATIONS_AGENT_TOKEN", "CLIENT_INVITE_TOKEN")}
        os.environ.update(tokens)
        os.environ.pop("RELEASE", None)
        from grok_invoices.entrypoints.http import app

        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
            server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
            thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
            thread.start()
            try:
                deadline = time.monotonic() + 45
                while not server.started and thread.is_alive() and time.monotonic() < deadline:
                    time.sleep(0.05)
                if not server.started:
                    raise RuntimeError("Isolated smoke server failed to start")
                asyncio.run(exercise(f"http://127.0.0.1:{port}", key, tokens))
            finally:
                server.should_exit = True
                thread.join(timeout=10)
                if thread.is_alive():
                    raise RuntimeError("Smoke server did not stop")


if __name__ == "__main__":
    main()
