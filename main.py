from fastapi import FastAPI

app = FastAPI(title="Grok Invoices", version="0.1.0")


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Welcome to Grok Invoices"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
