# Grok Invoices web

Next.js App Router, React, and Tailwind CSS. The web app runs separately from FastAPI and reads its public API through a same-origin, GET-only server proxy. No platform API key is required or exposed to the browser.

## Local development

Requires Node.js 22 or later. Start FastAPI from the repository root with `uv run uvicorn grok_invoices.entrypoints.http:app --reload`. In another terminal:

```powershell
cd apps/web
npm ci
npm run dev -- --hostname 127.0.0.1 --port 4173
```

Open http://127.0.0.1:4173. Stop with Ctrl+C. `API_BASE_URL` defaults to `http://127.0.0.1:8000`; set it in `.env.local` or the process environment to change the backend. This is runtime server configuration, not a `NEXT_PUBLIC_` variable.

```powershell
npm test
npm run build
npm start -- --hostname 127.0.0.1 --port 4173
```

## Separate web container

From the repository root:

```sh
docker build -t grok-invoices-web apps/web
docker run --rm -p 3000:3000 --network YOUR_SHARED_NETWORK -e API_BASE_URL=http://api:8000 grok-invoices-web
```

Replace the network and `api:8000` with the actual FastAPI container service and port. The image uses Next.js standalone output, runs as a non-root user, and exposes `/health`. In production, `deploy/deploy.sh` builds this image for every release and `deploy/compose.prod.yaml` runs it on `127.0.0.1:8011`. nginx sends `/` to it and sends `/api`, `/agents`, `/docs`, `/redoc`, `/openapi.json` and `/health` to FastAPI, so the browser reads `/api` from FastAPI directly there and the proxy in this app is only used in development.

## Data and capabilities

The dashboard reads invoices, questions, company context and recent events from FastAPI. It does not establish a live KSeF, telephone, or chat connection. Invoice decisions shown here are backend records, not frontend-generated tax advice.

The selected visual reference and provenance are in `../../docs/design/`. Automated tests cover domain transitions, CSV safety, API response validation and the read-only proxy boundary. Browser and container verification results are recorded separately in the project handoff.
