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

## Agent MCP servers

Three Grok Bots connect over stateless HTTP. Each server checks its own invite on every request. An empty setting refuses the connection.

- Invoice agent: `/agents/invoices/mcp`, setting `INVOICE_AGENT_TOKEN`
- Regulations agent: `/agents/regulations/mcp`, setting `REGULATIONS_AGENT_TOKEN`
- Client assistant: `/agents/client/mcp`, setting `CLIENT_INVITE_TOKEN`

Send the token as `?invite=` or the `X-Invite` header. Prefer the header, so the token stays out of the URL. Each token opens only its own server.

See [copy-ready prompts and setup](docs/grok-bot-setup.md) and the
[legal-validation runbook](docs/legal-validation.md). The regulations MCP can acquire official
ELI metadata, text and change pages. Retrieval is not legal approval or an installed watcher.

## Deployment

Every push to `main` deploys to https://grok.stackinghq.com through
`.github/workflows/deploy.yml`. The server builds the release, waits for `/health`
to pass, and rolls back to the previous release if it fails.

Put runtime secrets such as API keys in `/srv/grok-invoices/.env` on the server,
then redeploy. To persist data, write under `DATA_DIR` (`/data`), which survives deploys.

Changes to `deploy/` don't apply on push. To apply `compose.prod.yaml` or
`deploy.sh`, re-run `deploy/install.sh` on the server.
`install.sh` leaves an existing nginx site alone because certbot has edited it, so
copy changes to the `location` blocks in `deploy/nginx.conf` into
`/etc/nginx/sites-available/grok-invoices` by hand.

Each release runs two containers: FastAPI on `127.0.0.1:8010` and the dashboard on
`127.0.0.1:8011`. nginx sends `/api`, `/agents`, `/docs`, `/redoc`, `/openapi.json`
and `/health` to FastAPI, and everything else to the dashboard.

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

## Connect a client agent

Each client gets the same Grok Bot instructions and its own MCP link. The instructions
to paste into the bot are in `apps/api/client-agent-template.md`. Connecting with a
valid invite registers that client.

The server needs two settings in `/srv/grok-invoices/.env`:

- `CLIENT_INVITE_TOKEN`, the secret the bot sends as `?invite=` or the `X-Invite` header.
- `SECRET_ENCRYPTION_KEY`, a Fernet key for the KSeF token. Generate one with
  `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.

Point the bot at `https://grok.stackinghq.com/agents/client/mcp?invite=<token>`.
The platform API key is not accepted on this endpoint. A missing setting, a missing
invite, or a wrong invite is refused. The KSeF token is encrypted at rest. The API
returns only its last four characters. Submitted document text is available only through
the authenticated regulations MCP, not public reads.

## Project notes

- [Dashboard visual direction](docs/design/dashboard-direction.md)
- [Current context and demo scope](docs/project-context.md)
- [Polish accounting workflow and official sources](docs/research/polish-accounting-and-sources.md)
- [Keeping an AI agent's regulatory knowledge current](docs/research/ai-regulatory-knowledge.md)
- [Live source access checks and limitations](docs/research/source-checks.md)

Repository content and commit messages are written in English. Commit messages should stay short and descriptive.

## Dashboard development

The dashboard is a Next.js + Tailwind app in `apps/web/`, deployed in its own container beside FastAPI. It reads platform records through a server-side GET proxy. See [web setup and container configuration](apps/web/README.md).

Requires Node.js 22 or later and npm. From the repository root:

```powershell
cd apps/web
npm ci
npm run dev -- --hostname 127.0.0.1 --port 4173
```

Open http://localhost:4173. Stop the server with Ctrl+C. Run `npm test` for domain, adapter and proxy tests, and `npm run build` for the production bundle. `API_BASE_URL` defaults to the local FastAPI server at port 8000 and can be changed at runtime for a container network.
