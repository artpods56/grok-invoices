"""The client agent's MCP server. Connecting with a valid invite is registration.

Grok Bot reaches this through Cloudflare, which drops idle connections after about
100 seconds, so the transport is stateless HTTP with a JSON body and no SSE session.
"""

from collections.abc import Callable
from typing import Any

from fastmcp import FastMCP

from grok_invoices.entrypoints.mcp_common import bot_http_app, dump, guarded
from grok_invoices.service_layer import commands, services
from grok_invoices.settings import get_settings


def _call(action: Callable[[], Any]) -> Any:
    return dump(guarded(action))


mcp = FastMCP(
    "grok-invoices-client",
    instructions=(
        "You register one accounting client and relay that client's answers. "
        "You do not book invoices, choose accounts, interpret tax rules, or manage precedents."
    ),
)


@mcp.tool
def start_onboarding(nip: str, company_name: str) -> dict:
    """Register this client with their NIP and legal company name.

    Call this once you know both. The NIP is 10 digits. Spaces and hyphens are
    fine. The platform checks the checksum. If this returns an error, tell the
    client what is wrong and call it again with the corrected value.
    This does not connect KSeF and does not book anything.
    """
    return _call(lambda: services.start_onboarding(nip, company_name))


@mcp.tool
def configure_ksef(ksef_token: str) -> dict:
    """Store the client's KSeF token so the platform can download purchase invoices.

    The token comes from the Grok Bot vault and never from chat. Do not ask the
    client to paste it into the conversation, do not read it aloud, and do not
    repeat it back. Pass the vault secret as ksef_token. The platform encrypts
    it and this result only confirms the last four characters.
    """
    return _call(lambda: services.configure_ksef(ksef_token))


@mcp.tool
def submit_document(name: str, content_text: str) -> dict:
    """Store a document the client provided, as text, for the accounting agents.

    Use it for contracts, a vehicle list, or notes. The text limit is 1 MB.
    This does not book an invoice.
    """
    return _call(lambda: services.submit_document(name, content_text))


@mcp.tool
def list_open_questions() -> dict:
    """Questions the platform is waiting for the client to answer.

    The result is {"questions": [...]}. An empty list means nothing is waiting.
    Each item has the question text and the invoice it is about: vehicle plate,
    seller, gross amount and KSeF number. Read the plate and the amount to the
    client. Do not book the invoice.
    """
    return {"questions": _call(services.list_open_questions)}


@mcp.tool
def answer_question(question_id: int, answer: str) -> dict:
    """Record the client's answer and hand the case back to the accounting agents.

    Use the client's own words. Answering does not book the invoice, choose an
    account, or decide the VAT treatment.
    """
    return _call(lambda: services.answer_question(
        question_id, commands.AnswerQuestion(answer=answer, actor="client_agent"),
    ))


@mcp.tool
def get_status() -> dict:
    """Where onboarding stands.

    Reports the company name and NIP, whether a KSeF token is stored and its
    last four characters only, how many invoices are in each status, and how
    many questions are still open.
    """
    return _call(services.get_status)


client_mcp_app = bot_http_app(mcp, lambda: get_settings().client_invite_token)
