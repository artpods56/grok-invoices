"""MCP servers for the invoice bot and the regulations bot.

The platform does not call a model. Each tool parses arguments, calls a service,
and returns that result. The actor is fixed by the server.
"""

from fastmcp import FastMCP

from grok_invoices.domain.models import PrecedentConditions, ReceivedDocument, VehicleUsage
from grok_invoices.entrypoints.mcp_common import bot_http_app, dump, guarded
from grok_invoices.service_layer import commands, services
from grok_invoices.settings import get_settings

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
    return dump(guarded(lambda: services.sync_ksef("test")))


@invoices.tool
def add_invoice(ksef_number: str, xml: str) -> dict:
    """Store one FA(3) invoice already downloaded on your machine.

    Returns the new invoice, or says it was already stored.
    """
    added = guarded(lambda: services.ingest_documents([ReceivedDocument(ksef_number, xml.encode())]))
    if not added:
        return {"stored": False, "detail": "Invoice was already stored"}
    return {"stored": True, "invoice": dump(added[0])}


@invoices.tool
def list_pending_invoices() -> list[dict]:
    """Invoices still in status received."""
    return dump(services.list_invoices("received"))


@invoices.tool
def get_invoice(invoice_id: int) -> dict:
    """Summary, line items, and the vehicle plate read from the parsed invoice."""
    return guarded(lambda: _lines(invoice_id))


@_share(invoices, regulations)
def search_precedents(invoice_id: int) -> list[dict]:
    """Looking similar is not enough and only applicable counts.

    Best match first. applicable false means the platform will reject reuse. Read blockers.
    """
    return dump(guarded(lambda: services.search_precedents(invoice_id)))


@_share(invoices, regulations)
def list_accounts() -> list[dict]:
    """The client's chart of accounts."""
    return dump(services.list_accounts())


@invoices.tool
def post_by_rule(
    invoice_id: int, account: str, vat_deduction_percent: int, rationale: str, confidence: float,
) -> dict:
    """Book a simple invoice by rule. The server records the actor and source."""
    return dump(guarded(lambda: services.post_invoice(invoice_id, commands.PostInvoice(
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
    return dump(guarded(run))


@invoices.tool
def escalate(invoice_id: int, reason: str) -> dict:
    """Hand the invoice to the regulations agent. Put the blockers in the reason."""
    return dump(guarded(lambda: services.escalate_invoice(
        invoice_id, commands.Escalate(reason=reason, actor="invoice_agent"),
    )))


@_share(invoices, regulations)
def get_timeline(after_event_id: int = 0) -> list[dict]:
    """Timeline events with an id greater than after_event_id, oldest first."""
    return dump(services.list_events(after_event_id))


@regulations.tool
def list_open_cases() -> list[dict]:
    """Cases not yet resolved, each with its invoice summary and its questions."""
    return dump(services.list_open_cases())


@regulations.tool
def get_case(case_id: int) -> dict:
    """One case, its invoice summary, and every question asked on it."""
    return dump(guarded(lambda: services.get_case(case_id)))


@regulations.tool
def get_client_context() -> dict:
    """The client profile agents may use: fleet, facts, and accounts."""
    return dump(services.get_client())


@regulations.tool
def search_regulations(query: str) -> dict:
    """Search the VAT corpus. Only the returned provisions may be cited."""
    return dump(services.search_regulations(query))


@regulations.tool
def list_documents() -> list[dict]:
    """Documents the client submitted, without their text. Read one with get_document."""
    return dump(services.list_documents())


@regulations.tool
def get_document(document_id: int) -> dict:
    """The full text of one document the client submitted."""
    return dump(guarded(lambda: services.get_document(document_id)))


@regulations.tool
def ask_client(case_id: int, question: str) -> dict:
    """Ask the client one question about this case."""
    return dump(guarded(lambda: services.ask_client(
        case_id, commands.AskClient(text=question, actor="regulations_agent"),
    )))


@regulations.tool
def save_vehicle(plate: str, model: str, usage: VehicleUsage) -> dict:
    """Record a car the client confirmed is used by the company."""
    return dump(guarded(lambda: services.save_vehicle(commands.SaveVehicle(
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
    return dump(guarded(run))


invoices_app = bot_http_app(invoices, lambda: get_settings().invoice_agent_token)
regulations_app = bot_http_app(regulations, lambda: get_settings().regulations_agent_token)
