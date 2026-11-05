"""MCP servers for the invoice bot and the regulations bot.

The platform does not call a model. Each tool parses arguments, calls a service,
and returns that result. The actor is fixed by the server.
"""

import hashlib
import hmac
from collections.abc import Callable
from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from grok_invoices.domain.errors import DomainError
from grok_invoices.domain.models import PrecedentConditions, ReceivedDocument, VehicleUsage
from grok_invoices.service_layer import commands, services
from grok_invoices.settings import get_settings

_HTTP = {"path": "/mcp", "stateless_http": True, "json_response": True}


def _same_token(given: str, token: str | None) -> bool:
    """Constant-time invite check. An empty setting matches nothing.

    compare_digest rejects unequal lengths, so both sides are hashed first.
    A wrong token is then a 401, and the token itself is not logged.
    """
    if not token:
        return False
    return hmac.compare_digest(
        hashlib.sha256(given.encode()).digest(),
        hashlib.sha256(token.encode()).digest(),
    )


class RequireToken:
    """Refuse the connection unless this server's invite matches."""

    def __init__(self, app, get_token: Callable[[], str | None]):
        self.app = app
        self.get_token = get_token

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            request = Request(scope)
            given = request.query_params.get("invite") or request.headers.get("x-invite") or ""
            if not _same_token(given, self.get_token()):
                await JSONResponse({"detail": "Missing or invalid invite"}, status_code=401)(scope, receive, send)
                return
        await self.app(scope, receive, send)


def _call[T](fn: Callable[[], T]) -> T:
    try:
        return fn()
    except DomainError as error:
        raise ToolError(str(error)) from error


def _dump(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_dump(item) for item in value]
    if isinstance(value, dict):
        return {key: _dump(item) for key, item in value.items()}
    return value


def _lines(invoice_id: int) -> dict:
    detail = services.get_invoice(invoice_id)
    lines = []
    for row in detail.document.body.rows:
        rate = row.vat_rate.value if hasattr(row.vat_rate, "value") else row.vat_rate
        lines.append({
            "name": row.name,
            "quantity": None if row.quantity is None else str(row.quantity),
            "unit": row.unit_of_measure,
            "net": None if row.net_amount is None else str(row.net_amount),
            "vat": None if row.vat_amount is None else str(row.vat_amount),
            "vat_rate": str(rate),
            "gross": None if row.gross_amount is None else str(row.gross_amount),
        })
    summary = detail.model_dump(mode="json", exclude={"document", "postings", "cases"})
    summary["lines"] = lines
    return summary


invoices = FastMCP("grok-invoices-invoice-agent")
regulations = FastMCP("grok-invoices-regulations-agent")


def _share(*servers: FastMCP):
    def decorate(fn):
        for server in servers:
            server.tool(fn)
        return fn
    return decorate


@invoices.tool
def fetch_new_invoices() -> list[dict]:
    """Download new purchase invoices from KSeF TEST and store the ones not here yet."""
    return _dump(_call(lambda: services.sync_ksef("test")))


@invoices.tool
def add_invoice(ksef_number: str, xml: str) -> dict:
    """Store one FA(3) invoice already downloaded on your machine.

    Returns the new invoice, or says it was already stored.
    """
    added = _call(lambda: services.ingest_documents([ReceivedDocument(ksef_number, xml.encode())]))
    if not added:
        return {"stored": False, "detail": "Invoice was already stored"}
    return {"stored": True, "invoice": _dump(added[0])}


@invoices.tool
def list_pending_invoices() -> list[dict]:
    """Invoices still in status received."""
    return _dump(services.list_invoices("received"))


@invoices.tool
def get_invoice(invoice_id: int) -> dict:
    """Summary, line items, and the vehicle plate read from the parsed invoice."""
    return _call(lambda: _lines(invoice_id))


@_share(invoices, regulations)
def search_precedents(invoice_id: int) -> list[dict]:
    """Looking similar is not enough and only applicable counts.

    Best match first. applicable false means the platform will reject reuse. Read blockers.
    """
    return _dump(_call(lambda: services.search_precedents(invoice_id)))


@_share(invoices, regulations)
def list_accounts() -> list[dict]:
    """The client's chart of accounts."""
    return _dump(services.list_accounts())


@invoices.tool
def post_by_rule(
    invoice_id: int, account: str, vat_deduction_percent: int, rationale: str, confidence: float,
) -> dict:
    """Book a simple invoice by rule. The server records the actor and source."""
    return _dump(_call(lambda: services.post_invoice(invoice_id, commands.PostInvoice(
        account=account,
        vat_deduction_percent=vat_deduction_percent,
        rationale=rationale,
        confidence=confidence,
        actor="invoice_agent",
        source="rule",
    ))))


@invoices.tool
def post_by_precedent(invoice_id: int, precedent_id: int, rationale: str, confidence: float) -> dict:
    """Reuse a precedent. The account and the deduction percent come from the precedent itself."""
    def run():
        precedent = services.get_posting(precedent_id)
        return services.post_invoice(invoice_id, commands.PostInvoice(
            account=precedent.account,
            vat_deduction_percent=precedent.vat_deduction_percent,
            rationale=rationale,
            confidence=confidence,
            actor="invoice_agent",
            source="precedent",
            precedent_id=precedent_id,
        ))
    return _dump(_call(run))


@invoices.tool
def escalate(invoice_id: int, reason: str) -> dict:
    """Hand the invoice to the regulations agent. Put the blockers in the reason."""
    return _dump(_call(lambda: services.escalate_invoice(
        invoice_id, commands.Escalate(reason=reason, actor="invoice_agent"),
    )))


@_share(invoices, regulations)
def get_timeline(after_event_id: int = 0) -> list[dict]:
    """Timeline events with an id greater than after_event_id, oldest first."""
    return _dump(services.list_events(after_event_id))


@regulations.tool
def list_open_cases() -> list[dict]:
    """Cases not yet resolved, each with its invoice summary and its questions."""
    return _dump(services.list_open_cases())


@regulations.tool
def get_case(case_id: int) -> dict:
    """One case, its invoice summary, and every question asked on it."""
    return _dump(_call(lambda: services.get_case(case_id)))


@regulations.tool
def get_client_context() -> dict:
    """The client profile agents may use: fleet, facts, and accounts."""
    return _dump(services.get_client())


@regulations.tool
def search_regulations(query: str) -> dict:
    """Search the VAT corpus. Only the returned provisions may be cited."""
    return _dump(services.search_regulations(query))


@regulations.tool
def ask_client(case_id: int, question: str) -> dict:
    """Ask the client one question about this case."""
    return _dump(_call(lambda: services.ask_client(
        case_id, commands.AskClient(text=question, actor="regulations_agent"),
    )))


@regulations.tool
def save_vehicle(plate: str, model: str, usage: VehicleUsage) -> dict:
    """Record a car the client confirmed is used by the company."""
    return _dump(_call(lambda: services.save_vehicle(commands.SaveVehicle(
        plate=plate, model=model, usage=usage, actor="regulations_agent",
    ))))


@regulations.tool
def decide(
    case_id: int,
    account: str,
    vat_deduction_percent: int,
    rationale: str,
    confidence: float,
    legal_basis: str,
    conditions: PrecedentConditions | None = None,
) -> dict:
    """Book the case's invoice from the regulations and save it as a precedent.

    conditions takes vehicle_usage and vehicle_plate. legal_basis is required.
    """
    def run():
        case = services.get_case(case_id)
        return services.post_invoice(case.invoice.id, commands.PostInvoice(
            account=account,
            vat_deduction_percent=vat_deduction_percent,
            rationale=rationale,
            confidence=confidence,
            actor="regulations_agent",
            source="regulation",
            legal_basis=legal_basis,
            reusable=True,
            conditions=conditions or PrecedentConditions(),
        ))
    return _dump(_call(run))


invoices_app = invoices.http_app(
    **_HTTP,
    middleware=[Middleware(RequireToken, get_token=lambda: get_settings().invoice_agent_token)],
)
regulations_app = regulations.http_app(
    **_HTTP,
    middleware=[Middleware(RequireToken, get_token=lambda: get_settings().regulations_agent_token)],
)
