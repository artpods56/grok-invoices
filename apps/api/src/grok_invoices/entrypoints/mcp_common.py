"""What the bots' MCP servers share: the invite check, the transport and reporting results."""

import hashlib
import hmac
from collections.abc import Callable
from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from grok_invoices.domain.errors import DomainError


def _same_token(given: str, token: str | None) -> bool:
    """Constant-time check. A missing setting matches nothing, so that server refuses everyone."""
    if not token:
        return False
    return hmac.compare_digest(hashlib.sha256(given.encode()).digest(), hashlib.sha256(token.encode()).digest())


class RequireToken:
    """Refuse the connection unless this server's invite matches. The setting is read per request."""

    def __init__(self, app: Any, get_token: Callable[[], str | None]) -> None:
        self.app = app
        self.get_token = get_token

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] == "http":
            request = Request(scope)
            given = request.query_params.get("invite") or request.headers.get("x-invite") or ""
            if not _same_token(given, self.get_token()):
                await JSONResponse({"detail": "Missing or invalid invite"}, status_code=401)(scope, receive, send)
                return
        await self.app(scope, receive, send)


def bot_http_app(server: FastMCP, get_token: Callable[[], str | None]) -> Starlette:
    """Stateless HTTP with JSON responses, because Cloudflare cuts idle connections after about 100 seconds."""
    return server.http_app(
        path="/mcp", stateless_http=True, json_response=True,
        middleware=[Middleware(RequireToken, get_token=get_token)],
    )


def guarded[T](action: Callable[[], T]) -> T:
    """Report a refusal as a tool error, so the bot can read why and recover."""
    try:
        return action()
    except DomainError as error:
        raise ToolError(str(error)) from error


def dump(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [dump(item) for item in value]
    if isinstance(value, dict):
        return {key: dump(item) for key, item in value.items()}
    return value
