<img src="assets/icon.svg" width="64" height="64" alt="">

# Grok Invoices

Grok Invoices: first of its kind Agent as a Service. A platform where agents book purchase invoices from KSeF and an accountant supervises.

## Run locally

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run:

```sh
uv sync --locked
uv run uvicorn grok_invoices.entrypoints.http:app --reload
```

The server runs at http://127.0.0.1:8000, with interactive API docs at `/docs`.
See [AGENTS.md](AGENTS.md) for the architecture and conventions.

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
[`/docs`](https://grok.stackinghq.com/docs) and `/openapi.json`.

Writes need `Authorization: Bearer $PLATFORM_API_KEY`. The key is in `/srv/grok-invoices/.env`
on the server; locally, leave it unset to skip the check.

- `POST /api/demo/issue-fuel-invoice` issues the stage demo's invoice on KSeF TEST.
- `POST /api/ksef/sync?source=test` fetches new invoices from KSeF TEST.
- `POST /api/ksef/sync` loads three fixture invoices, as a fallback if KSeF TEST is down.
- `POST /api/demo/reset` restores the seed so the demo can run again.

Bumping `STORE_VERSION` in `unit_of_work.py` rebuilds the database from the seed on the next
start, which discards existing data.
