# Agent backend

The backend extends the existing FastAPI/SQLite platform. There is no second invoice or case database, no database schema change, and no automatic deployment in this task.

## Implemented flow

1. An explicit mock KSeF sync or MCP document submission adds structured invoices.
2. The invoice agent proposes an expense category. The regulatory agent reviews non-trivial cases against the supplied synthetic policy and company facts.
3. `store.py` validates the document, policy version, application dates, vehicle scope and current context before applying a proposal. Agents cannot choose amounts, accounts or VAT percentages through the proposal schema.
4. A missing vehicle creates a case-linked question. The client assistant reads it, collects structured facts and submits an answer.
5. A complete matching answer updates the vehicle and purpose with audit events, then resumes the same case. An incomplete answer leaves the question open. A different replay is rejected; an identical replay does not duplicate the decision.
6. A supported decision records the synthetic policy, source link and conditional precedent. A subsequent invoice for that vehicle can reuse it without another question. A policy/vehicle/date mismatch prevents reuse.

No accountant approval is required for this bounded simulation. Existing accountant takeover and correction routes remain available. An exclusive-business-use declaration alone does not authorize 100% vehicle VAT: that branch is blocked pending additional evidence.

`GET /api/agents/status` normalizes the platform's storage states into `pending`, `completed`, `waiting_for_client`, and `blocked`. The original case table retains its existing `open`, `waiting_for_client`, and `resolved` states. A blocked agent outcome is an audit event and projection, not a new SQLite enum. The response includes questions, their decision links, and monetary values as decimal strings.

## Local demo

Install dependencies and start the app using the root README. The following calls modify only the server you address; use a local instance for preparation. `PLATFORM_API_KEY` protects REST writes when configured.

```sh
curl -X POST http://127.0.0.1:8000/api/agents/setup-demo
curl -X POST http://127.0.0.1:8000/api/ksef/sync
curl -X POST http://127.0.0.1:8000/api/agents/run \
  -H 'Content-Type: application/json' -d '{"mode":"demo"}'
curl http://127.0.0.1:8000/api/questions?status=open
```

New databases contain the synthetic policy in the seed. Existing databases require the explicit `setup-demo` call, restricted to the seeded demo company. It preserves invoices, questions and existing postings. No reset is needed. Seed changes take effect only on a fresh database or an explicitly requested demo reset.

Answer the returned question using its actual ID:

```sh
curl -X POST http://127.0.0.1:8000/api/agents/questions/QUESTION_ID/answer \
  -H 'Content-Type: application/json' \
  -d '{"vehicle_plate":"GD 9R247","usage":"mixed","business_purpose":"Travel to a client site"}'
```

`usage` accepts `mixed`, `company`, or `private`. Only the mixed-use fuel branch has a supported synthetic rule. The current demo policy supports October-November 2026 fixture invoices with `-DEMO-` identities. It does not certify real documents or current tax-law interpretation.

## Grok Bot MCP connection

The official Python MCP SDK serves Streamable HTTP at `/mcp` in the same app. It supports initialization, tool discovery and calls, with six client-facing tools:

- `start_onboarding`: reports the already seeded company and setup capabilities.
- `configure_ksef`: explicitly reports that live KSeF/vault setup is unavailable; accepts no credentials.
- `submit_document`: accepts an `InvoiceIn` object, deduplicates it and starts backend processing.
- `list_open_questions`: returns linked questions and required answer fields.
- `answer_question`: accepts a question ID and structured vehicle answer, then resumes processing.
- `get_status`: returns the platform result, evidence and refresh timestamp for chat or Pages.

Use `Authorization: Bearer <MCP_INVITE_TOKEN>` for the client connection, or the platform key for an operator. Query-string credentials are deliberately unsupported to keep them out of access logs. An MCP invitation does not authorize REST writes. When neither key is configured, authentication is skipped for local development only; deployed startup still requires the platform key.

This checkout is a single-company demo. The connection is scoped to that company, tools accept no company selector, and `start_onboarding` does not create tenants. It is not a completed multi-tenant registration system. Public REST reads retain their upstream demo-only contract. Do not store real company documents or secrets.

The client assistant's instructions are in `mcp_server.py`. It gathers facts and displays server results; accounting and regulatory workers run behind the platform. A client tool never supplies a posting directly.

## Agent modes

- `demo`: deterministic synthetic role proposals, with no external model call. This is the default and is explicitly identified in results/events.
- `xai`: separate invoice-triage and regulatory-review prompts through xAI Chat Completions with schema-validated output. Set `XAI_API_KEY` and optionally `XAI_MODEL` (default `grok-4.7`). Provider errors or invalid output block the case; they never fall back to demo mode.

REST chooses the mode in `/api/agents/run`; the answer endpoint accepts `?mode=xai`. MCP uses the server's `AGENT_MODE=demo|xai`. Model requests occur outside SQLite write transactions; a context fingerprint prevents committing a decision after the underlying facts changed.

Both modes use the same synthetic rule pack. xAI mode is model-assisted fixture processing, not unrestricted legal interpretation or online regulatory monitoring. No live xAI request has been verified by the implementation tests; its wire contract is tested with a mock transport.

## Remaining integrations

- Real KSeF ingestion and a vault-to-platform secret bridge. Structured document submission is not XML/PDF extraction.
- Validated, versioned production legal evidence. The source URL in the fixture policy is a reference, not proof of provision-level applicability.
- Proactive Grok Bot wake-up, phone calls, and actual Page creation/refresh. Open-question polling alone does not provide push notifications.
- Multi-company authorization, private read APIs, filing/payment providers, and full-accounting coverage.

These limitations are exposed rather than replaced with invented success states. No background scheduler, real call, filing or payment is started.

## Verification

Run `uv run pytest -q`. Tests cover the existing platform API, complete agent demo, partial and duplicate answers, subsequent precedent reuse, changed policy, stale model context, unsupported full-VAT requests, accountant takeover, provider failure, and the actual MCP HTTP protocol. The fixture source policy is synthetic throughout.

Run `uv run python -m scripts.smoke_agents` for a real localhost HTTP round trip with the official MCP client. It creates its own temporary database and ephemeral port, initializes MCP, discovers six tools, resolves the fuel question and replays the answer. The server stops afterwards. It does not use the deployed application or existing local demo state.

Technical references: [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk), [xAI structured outputs](https://docs.x.ai/developers/model-capabilities/text/structured-outputs).
