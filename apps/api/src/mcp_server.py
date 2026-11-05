"""Client-facing MCP tools for one authorized demo company, backed by platform state."""

import hmac
import os

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.datastructures import Headers
from starlette.responses import JSONResponse

from apps.api.src import agents, store
from apps.api.src.db import read, transaction
from apps.api.src.schemas import ContextAnswerIn, InvoiceIn

INSTRUCTIONS = (
    "You are the client's assistant. Collect documents and facts, relay open questions, "
    "and explain platform results. Do not interpret law, choose VAT treatment, or create postings. "
    "Use get_status for evidence. Pages are read-only projections, not the source of truth. "
    "Do not request KSeF tokens in chat. This server holds synthetic data for one demo company."
)

def create_mcp() -> FastMCP:
    server = FastMCP(
        "Grok Invoices", instructions=INSTRUCTIONS, stateless_http=True, json_response=True,
        streamable_http_path="/mcp",
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=["127.0.0.1:*", "localhost:*", "testserver", "grok.stackinghq.com"],
            allowed_origins=["http://127.0.0.1:*", "http://localhost:*", "https://grok.stackinghq.com"],
        ),
    )
    for tool in (start_onboarding, configure_ksef, submit_document, list_open_questions, answer_question, get_status):
        server.add_tool(tool)
    return server


class MCPAuthMiddleware:
    """Authorize the MCP connection, including reads and initialization."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("path", "").rstrip("/") == "/mcp":
            keys = [v for v in (os.environ.get("MCP_INVITE_TOKEN"), os.environ.get("PLATFORM_API_KEY")) if v]
            authorization = Headers(scope=scope).get("authorization", "").encode()
            if keys and not any(hmac.compare_digest(authorization, f"Bearer {key}".encode()) for key in keys):
                await JSONResponse({"detail": "Missing or invalid MCP credentials"}, status_code=401,
                                   headers={"WWW-Authenticate": "Bearer"})(scope, receive, send)
                return
        await self.app(scope, receive, send)


def _mode() -> str:
    mode = os.environ.get("AGENT_MODE", "demo")
    if mode not in ("demo", "xai"):
        raise ValueError("AGENT_MODE must be demo or xai")
    return mode


def start_onboarding() -> dict:
    """Return the demo company's scope and required setup; this does not create another tenant."""
    with read() as conn:
        client = store.get_client(conn)
        return {"company": client, "single_company_demo": True, "policy_ready": store.agent_policy(conn) is not None,
                "ksef": "mock_only", "instructions": INSTRUCTIONS}


def configure_ksef() -> dict:
    """Report the KSeF connector capability. Never pass a raw credential to this tool."""
    return {"status": "blocked", "reason": "Live KSeF and a secret-aware vault bridge are not configured",
            "accepts_credentials": False, "available_source": "Explicit mock sync through the platform API"}


def submit_document(invoice: InvoiceIn) -> dict:
    """Submit a structured purchase invoice, deduplicate by identity, and start backend processing."""
    with transaction() as conn:
        saved = store.submit_agent_document(conn, invoice)
    return agents.run_invoice(saved["id"], _mode())


def list_open_questions() -> list[dict]:
    """Read case-linked questions. Polling does not provide proactive phone notifications."""
    with read() as conn:
        return store.agent_questions(conn)


def answer_question(question_id: int, answer: ContextAnswerIn) -> dict:
    """Record structured vehicle facts and resume the same case; incomplete answers stay open."""
    return agents.answer_and_resume(question_id, answer, _mode())


def get_status(invoice_id: int | None = None) -> dict:
    """Read platform decisions and reasons for chat/Pages; does not itself create a Page."""
    with read() as conn:
        invoices = [store.agent_result(conn, invoice_id)] if invoice_id else [
            store.agent_result(conn, i["id"]) for i in store.list_invoices(conn, None)
        ]
        return {"company": store.get_client(conn), "invoices": invoices, "refreshed_at": store._now(),
                "simulation": True, "open_questions": store.agent_questions(conn)}
