<img src="assets/icon.svg" width="64" height="64" alt="">

# Grok Invoices

A simple FastAPI application managed with uv and Python 3.13.

## Run locally

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run:

```sh
uv sync --locked
uv run uvicorn main:app --reload
```

The server runs at http://127.0.0.1:8000.

- `GET /` returns a welcome message.
- `GET /health` returns `{"status": "ok"}`.
- `/docs` provides interactive API documentation.
- `/redoc` provides alternative API documentation.
- `/openapi.json` provides the API schema.

Add dependencies with `uv add <package>`. Commit `uv.lock` to keep installations
reproducible. uv manages the local `.venv` automatically.

## Deployment

Every push to `main` deploys to https://grok.stackinghq.com through
`.github/workflows/deploy.yml`. The server builds the release, waits for `/health`
to pass, and rolls back to the previous release if it fails.

Put runtime secrets such as API keys in `/srv/grok-invoices/.env` on the server,
then redeploy. To persist data, write under `DATA_DIR` (`/data`), which survives deploys.

Changes to `deploy/` don't apply on push. To apply `compose.prod.yaml` or
`deploy.sh`, re-run `deploy/install.sh` on the server.

## Platform API

The shared state agents work through lives under `/api`. The contract is at
[`/docs`](https://grok.stackinghq.com/docs) and `/openapi.json`. Run the tests with `uv run pytest`.

Writes need `Authorization: Bearer $PLATFORM_API_KEY`. The key is in `/srv/grok-invoices/.env`
on the server; locally, leave it unset to skip the check.

- `POST /api/ksef/sync` loads the three demo invoices (mock KSeF).
- `POST /api/demo/reset` restores the seed so the demo can run again.

A schema change in `apps/api/src/db.py` rebuilds the database from the seed on the next start,
which discards existing data.
