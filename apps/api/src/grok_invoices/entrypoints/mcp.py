"""The client agent's MCP server. Connecting with a valid invite is registration.

Grok Bot reaches this through Cloudflare, which drops idle connections after about
100 seconds, so the transport is stateless HTTP with a JSON body and no SSE session.
"""

import hmac
import logging
import re
from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from grok_invoices.domain.errors import DomainError
from grok_invoices.service_layer import commands, services
from grok_invoices.settings import get_settings

_INVITE_IN_URL = re.compile(r"(invite=)[^&\s\"']+")


class _RedactInvite(logging.Filter):
    """Uvicorn logs the request path, which is where the invite arrives.

    The path is usually a %-format argument, so scrub the rendered line. Editing
    the format string in place would eat the placeholder and break logging.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if not _record_has_invite(record):
            return True
        try:
            rendered = record.getMessage()
        except Exception:
            rendered = str(record.msg)
        record.msg = _scrub(rendered)
        record.args = ()
        return True


def _scrub(value: str) -> str:
    return _INVITE_IN_URL.sub(r"\1[redacted]", value)


def _record_has_invite(record: logging.LogRecord) -> bool:
    if isinstance(record.msg, str) and "invite=" in record.msg:
        return True
    args = record.args
    if isinstance(args, tuple):
        return any(isinstance(arg, str) and "invite=" in arg for arg in args)
    if isinstance(args, dict):
        return any(isinstance(value, str) and "invite=" in value for value in args.values())
    return False


def redact_invite_from_logs() -> None:
    redact = _RedactInvite()
    loggers = [logging.getLogger(name) for name in ("", "uvicorn", "uvicorn.access", "uvicorn.error")]
    for logger in loggers:
        if not any(isinstance(existing, _RedactInvite) for existing in logger.filters):
            logger.addFilter(redact)
        for handler in logger.handlers:
            if not any(isinstance(existing, _RedactInvite) for existing in handler.filters):
                handler.addFilter(redact)


class RequireToken:
    """Invite check for MCP. The platform API key is not accepted here.

    The setting is read on each request, so a missing setting refuses everything
    and tests can change it without restarting the process.
    """

    def __init__(self, app: Any, get_token: Any) -> None:
        self.app = app
        self.get_token = get_token

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] == "http":
            request = Request(scope)
            given = request.query_params.get("invite") or request.headers.get("x-invite") or ""
            token = self.get_token()
            if not token or not hmac.compare_digest(given.encode(), token.encode()):
                await JSONResponse({"detail": "Missing or invalid invite"}, status_code=401)(scope, receive, send)
                return
        await self.app(scope, receive, send)


def _call(action: Any) -> Any:
    try:
        value = action()
    except DomainError as error:
        raise ToolError(str(error)) from error
    if isinstance(value, list):
        return [_dump(item) for item in value]
    return _dump(value)


def _dump(value: Any) -> Any:
    dump = getattr(value, "model_dump", None)
    if dump is None:
        return value
    return dump(mode="json")


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


client_mcp_app = mcp.http_app(
    path="/mcp",
    stateless_http=True,
    json_response=True,
    middleware=[Middleware(RequireToken, get_token=lambda: get_settings().client_invite_token)],
)
