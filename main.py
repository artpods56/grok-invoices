import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from apps.api.src.api import router
from apps.api.src.db import init_db, transaction
from apps.api.src.seed import seed_if_empty
from apps.api.src.mcp_server import MCPAuthMiddleware, create_mcp


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    # RELEASE is only set on the server. Failing here makes the deploy roll back.
    if os.environ.get("RELEASE") and not os.environ.get("PLATFORM_API_KEY"):
        raise RuntimeError("PLATFORM_API_KEY must be set when deployed")
    init_db()
    with transaction() as conn:
        seed_if_empty(conn)
    async with application.state.mcp.session_manager.run():
        yield


async def root() -> dict[str, str]:
    return {"message": "Welcome to Grok Invoices"}


async def health() -> dict[str, str]:
    return {"status": "ok"}


def create_app() -> FastAPI:
    application = FastAPI(title="Grok Invoices", version="0.1.0", lifespan=lifespan)
    application.state.mcp = create_mcp()
    application.include_router(router)
    application.add_middleware(MCPAuthMiddleware)
    application.add_api_route("/", root, methods=["GET"])
    application.add_api_route("/health", health, methods=["GET"])
    # Keep the SDK's own transport. Existing REST routes win over the final mount.
    application.mount("/", application.state.mcp.streamable_http_app())
    return application


app = create_app()
