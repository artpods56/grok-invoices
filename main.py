import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from apps.api.src.api import router
from apps.api.src.db import init_db, transaction
from apps.api.src.seed import seed_if_empty


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # RELEASE is only set on the server. Failing here makes the deploy roll back.
    if os.environ.get("RELEASE") and not os.environ.get("PLATFORM_API_KEY"):
        raise RuntimeError("PLATFORM_API_KEY must be set when deployed")
    init_db()
    with transaction() as conn:
        seed_if_empty(conn)
    yield


app = FastAPI(title="Grok Invoices", version="0.1.0", lifespan=lifespan)
app.include_router(router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Welcome to Grok Invoices"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
