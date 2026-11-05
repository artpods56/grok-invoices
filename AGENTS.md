<<<<<<< HEAD
# Repository conventions

- Write all repository content in English, including documentation, code comments, fixtures, and commit messages. Conversation with the project owner may remain in Polish.
- Keep commit messages short, simple, and descriptive.
- The web application belongs in `apps/web/`.
- Commit completed, coherent changes regularly and keep the project Outline document current with decisions, progress, verification, and commit references. Read the latest document before editing and preserve unrelated content.
- Distinguish implemented behavior, verified external behavior, synthetic demo data, and proposals. Do not describe a research note as a working integration.
- Preserve the hackathon build history. The submission requires authentic AI session exports under `/sessions`; never fabricate an export or include credentials in it.
=======
# AGENTS.md

Grok Invoices is a hackathon demo of AI agents processing purchase invoices. This repo holds
the shared platform they work through: a FastAPI app with SQLite storage, managed with uv on
Python 3.13.

## Commands

```sh
uv sync --locked                 # install dependencies
uv run uvicorn main:app --reload # run at http://127.0.0.1:8000
uv run pytest -q                 # run the tests
uv add <package>                 # add a dependency, and commit uv.lock
```

Local data lives in `.data/`. Leave `PLATFORM_API_KEY` unset locally to skip the write check.

## Layout

- `main.py`: app entry point, startup, `/` and `/health`.
- `apps/api/src/api.py`: HTTP routes under `/api` and the API key check.
- `apps/api/src/store.py`: business rules and all queries.
- `apps/api/src/schemas.py`: request and response models.
- `apps/api/src/db.py`: SQLite schema and connections.
- `apps/api/src/seed.py`: demo data and the mock KSeF inbox.
- `tests/test_platform.py`: API tests, including the full demo scenario.
- `deploy/`: server scripts and compose file. See the warning below.

## Pushing to `main` deploys to production

Every push to `main` runs the tests, then deploys to https://grok.stackinghq.com, even when
only docs changed. There is no staging. If the new release fails its health check, the server
rolls back to the previous one.

- Run `uv run pytest -q` before you push.
- Changing `SCHEMA` in `apps/api/src/db.py` deletes the production database on the next start
  and rebuilds it from the seed. Say so in the commit message.
- The app won't start on the server without `PLATFORM_API_KEY`.
- `deploy/` changes don't apply on push. Someone has to re-run `deploy/install.sh` on the server.

## Rules for changing the code

- Keep business rules in `store.py`, not in routes or agents. The API must refuse an invalid
  action even when an agent asks for it. For example, it returns 409 when an agent reuses a
  precedent that doesn't apply.
- Do each write inside `transaction()`, and record it with `log_event` so that the state and
  the timeline commit together.
- Add or update a test in `tests/test_platform.py` when a rule or the demo flow changes.
- Build against the existing API. The contract is at `/docs` and `/openapi.json`. Don't add a
  second store of invoices, cases or precedents.
- Writes need `Authorization: Bearer $PLATFORM_API_KEY`. Reads are public, so store only demo
  data, and never commit secrets. On the server, the key is in `/srv/grok-invoices/.env`.
- The server is shared with other services. Touch only `/srv/grok-invoices`.

## Demo data

- `POST /api/ksef/sync` loads the three demo invoices.
- `POST /api/demo/reset` restores the seed. It wipes the state of anyone using production, so
  check first that no demo is running.
>>>>>>> origin/main
