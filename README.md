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

## Project notes

- [Dashboard visual direction](docs/design/dashboard-direction.md)
- [Current context and demo scope](docs/project-context.md)
- [Polish accounting workflow and official sources](docs/research/polish-accounting-and-sources.md)
- [Keeping an AI agent's regulatory knowledge current](docs/research/ai-regulatory-knowledge.md)
- [Live source access checks and limitations](docs/research/source-checks.md)

Repository content and commit messages are written in English. Commit messages should stay short and descriptive.

## Dashboard development

The dashboard implementation is in `apps/web/`. It uses synthetic fixtures; live KSeF, Grok Bot, phone calls, and autonomous accounting are not connected by this frontend.

Requires Node.js 22 or later and npm. From the repository root:

```powershell
cd apps/web
npm ci
npm run dev -- --host 127.0.0.1 --port 4173 --strictPort
```

Open http://localhost:4173. Stop the server with Ctrl+C. Run `npm test` for domain and static-host tests, and `npm run build` for the production bundle. The local demo state resets on page reload.

Created in [T3 Code](https://t3.codes).
=======
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
>>>>>>> origin/main
