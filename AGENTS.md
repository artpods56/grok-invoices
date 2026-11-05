# AGENTS.md

Grok Invoices is a hackathon demo of AI agents processing purchase invoices from KSeF. This
repo holds the shared platform they work through: a FastAPI app with SQLite storage, managed
with uv on Python 3.13. The invoice model comes from ksef2, our own KSeF SDK.

The platform is the agents' office, their ERP. All agents run as Grok Bots, each connecting
through its own dedicated MCP server, so MCP tools are the main way in. HTTP and the accountant
view exist so that humans can supervise. The platform holds state and enforces rules, and it
never calls a model itself.

The Outline docs "Grok Invoices: koncepcja projektu" and "Demo: telefon po fakturze
paliwowej" describe the product and the stage demo.

## Commands

```sh
uv sync --locked                 # install dependencies
uv run uvicorn grok_invoices.entrypoints.http:app --reload  # run at http://127.0.0.1:8000
uv run pytest -q                 # run the tests (no network)
uv run pytest -m live -o addopts=""  # run the real flow against KSeF TEST
uv add <package>                 # add a dependency, and commit uv.lock
```

Local data lives in `.data/`. Leave `PLATFORM_API_KEY` unset locally to skip the write check.

## Layout

Code lives in `apps/api/src/grok_invoices`. Dependencies only point inward, and
`test_foundation.py` fails the build if they don't.

- `domain/models.py`: supplementary models and their behaviour: what KSeF doesn't cover.
- `domain/rules.py`: accounting rules that hold whatever an agent's model decides.
- `service_layer/services.py`: the use cases. Every entrypoint calls these.
- `service_layer/commands.py`, `views.py`: what services take and return.
- `service_layer/unit_of_work.py`: the SQLite transaction and repositories.
- `entrypoints/http.py`: FastAPI app, routes under `/api`, the API key check, `/health`.
- `entrypoints/mcp_agents.py`: FastMCP servers for the invoice and regulations bots, with the actor fixed per server.
- `ksef.py`: KSeF TEST calls through ksef2.
- `seed.py`: demo data and fixture invoices.
- `settings.py`: configuration from the environment.
- `apps/api/tests/`: tests, including the full demo scenario in `test_platform.py`.
- `deploy/`: server scripts and compose file. See the warning below.

## Pushing to `main` deploys to production

Every push to `main` runs the tests, then deploys to https://grok.stackinghq.com, even when
only docs changed. There is no staging. If the new release fails its health check, the server
rolls back to the previous one.

- Run `uv run pytest -q` before you push.
- Bumping `STORE_VERSION` in `unit_of_work.py` deletes the production database on the next
  start and rebuilds it from the seed. Say so in the commit message.
- The app won't start on the server without `PLATFORM_API_KEY`.
- `deploy/` changes don't apply on push. Someone has to re-run `deploy/install.sh` on the server.

## Rules for changing the code

- Use ksef2 directly. `KsefInvoice` is the invoice model, read through `Invoice.document`.
  Don't write providers, adapters or mappers around the SDK, and don't re-model its fields.
  Docs: https://docs.stackinghq.com/ksef2/sdk/getting-started/overview/
- Build MCP servers with FastMCP (https://gofastmcp.com), stateless with JSON responses, because
  Cloudflare cuts idle connections.
- Add an abstraction only for a second real implementation. There are no abstract repositories
  or fake units of work, because SQLite is the only store and tests run on it in milliseconds.
  Something tests must not trigger, like a model or phone call, gets a plain function or
  `Protocol` as its seam.
- Keep business rules in `domain/`, not in routes, MCP tools or agent prompts. The API must
  refuse an invalid action even when an agent asks for it. For example, it returns 409 when an
  agent reuses a precedent that doesn't apply.
- Entrypoints only parse input, call a service and return its result, so HTTP, MCP and agents
  all get the same rules.
- Do each write in one `UnitOfWork`, inside a service, and record it with a timeline `Event` so
  that the state and the timeline commit together. Loaded entities save themselves on commit.
- Never make a network call inside a `UnitOfWork`, because it blocks all other writers.
- Models persist as JSON, so an optional field needs no migration. Bump `STORE_VERSION` only if
  stored data would stop loading.
- Add or update a test when a rule or the demo flow changes.
- Build against the existing API. The contract is at `/docs` and `/openapi.json`. Don't add a
  second store of invoices, cases or precedents.
- Writes need `Authorization: Bearer $PLATFORM_API_KEY`. Reads are public, so store only demo
  data, never return secrets or contact details (return a view, like `ClientProfile`, rather
  than the model that holds them), and never commit secrets. On the server, secrets are in `/srv/grok-invoices/.env`;
  read them through `settings.py`.
- The server is shared with other services. Touch only `/srv/grok-invoices`.
- Don't use `from __future__` imports.

## Demo data

- The stage demo depends on `GD 9R247` staying off the seed fleet.
- VAT on a fuel invoice is always 23%. The 50% is a deduction decided in the posting, never a KSeF field.
- `POST /api/demo/issue-fuel-invoice` issues the stage invoice on KSeF TEST, and
  `POST /api/ksef/sync?source=test` fetches it.
- `POST /api/ksef/sync` loads three fixture invoices, as a fallback if KSeF TEST is down.
- `POST /api/demo/reset` restores the seed. It wipes the state of anyone using production, so
  check first that no demo is running.
