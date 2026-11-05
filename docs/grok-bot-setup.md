# Grok Bot setup

Based on Outline concept revision 33 and stage-demo revision 8, read on 2026-11-05.
The copy-ready Outline card is [Grok Bot setup — prompts and MCP](https://outline.stackinghq.com/doc/grok-bot-setup-prompts-and-mcp-Bf7mRPwe1F).

## Three bots, three connections

Create three Grok Bots. Paste the corresponding full prompt into each bot's setup instructions.
The platform never calls a model; the bots execute these instructions through MCP.

| Bot and prompt | HTTPS MCP endpoint | Private server setting |
| --- | --- | --- |
| [Invoice Agent](../apps/api/invoice-agent-template.md) | `https://grok.stackinghq.com/agents/invoices/mcp` | `INVOICE_AGENT_TOKEN` |
| [Regulations Agent](../apps/api/regulations-agent-template.md) | `https://grok.stackinghq.com/agents/regulations/mcp` | `REGULATIONS_AGENT_TOKEN` |
| [Client Assistant](../apps/api/client-agent-template.md) | `https://grok.stackinghq.com/agents/client/mcp` | `CLIENT_INVITE_TOKEN` |

Use Streamable HTTP. Prefer the private `X-Invite` header where the connector supports it;
otherwise append `?invite=<ROLE_SECRET>` privately in the connector. Never put actual invites
into repository files, screenshots, shared chat or Outline. The three values must differ.
`PLATFORM_API_KEY` is for administrator REST writes, not for these MCP connections.
An absent/wrong invite or absent server setting returns 401. Access logs must stay disabled.
Grok Bot runs in the cloud, so use public HTTPS rather than localhost.

This is a single-company demo. Separate role tools do not make it a multi-tenant production
system, and bots on one Grok Bot account share a cloud computer. Do not give them administrator
credentials or store role secrets in shared files.

## Server configuration

Set the three invite settings privately on the server. Set `SECRET_ENCRYPTION_KEY` to a
Fernet key before onboarding a KSeF token. See `.env.example` for names only. Store actual
values in `/srv/grok-invoices/.env`. Never print them into session exports.

Use Grok Bot's private vault-to-tool mechanism for `configure_ksef(ksef_token)`. Stop that
step if the client cannot pass the vault secret privately; do not paste a token in chat.
The platform verifies it against KSeF TEST outside a database transaction, encrypts it at
rest and returns only its last four characters. The complete vault-to-MCP path still needs
acceptance in a real Grok Bot session.

## First messages

Invoice Agent:

> Discover your MCP tools, list pending invoices and inspect their details and precedent blockers. Do not fetch external invoices or write postings yet. Report readiness and actual IDs.

Regulations Agent:

> Discover your MCP tools, read open cases and client context. Report available official-source tools and missing evidence. Do not decide a case during this connection check.

Client Assistant:

> Call get_status and list_open_questions. Introduce yourself in Polish and ask the first actual open question. Do not change the company identity or configure a token during this connection check.

The expected tool counts are 10 for invoices, 16 for regulations and 6 for the client.
Discovery is authoritative: report missing tools, a 401, a redirect or a transport error
instead of claiming that a bot is connected. Do not reset production to test a connection.

## Running the demo

Use an isolated local platform for preparation. An explicit local `POST /api/ksef/sync`
loads the three synthetic fixture invoices. The full local transport smoke is:

```sh
uv sync --locked
uv run pytest -q
uv run python -m scripts.smoke_agents
```

The smoke uses a temporary database and a loopback port. It does not call a model, Grok Bot,
ELI, KSeF or production, and does not reset an existing database.

In the bots, explicitly request each pass: invoice processing, regulatory case review,
client question collection, then regulatory resumption after the answer. The full fixture
scenario includes simple IT, known-vehicle precedent, unknown vehicle and later reuse.
The stage narrative focuses on the unknown `GD 9R247` vehicle. Keep it out of the seed fleet.
The Polish phone hook is narrated; use chat rather than attempting a +48 call.

`list_open_questions` is a read, not a push trigger. Saving an answer resumes the platform
case, not a Grok Bot process. Automatic wake-up, recurring scans and Page refresh require a
separate supported trigger and an observed acceptance run. Do not use an endless polling loop.

## Current legal-source MCP

Only the Regulations Agent gets the following read-only tools. No separate ELI API key is needed.

| Tool | Result and limit |
| --- | --- |
| `search_regulations(query)` | Simplified synthetic examples; explicitly non-authoritative and not legally validated. |
| `search_legal_acts(title, offset=0, limit=25)` | Official ELI title search, all statuses; follow `next_offset`. |
| `get_legal_act(eli)` | Official metadata, dates, references and publication URL for e.g. `DU/2004/535`. |
| `read_legal_text(eli, article=None, offset=0)` | Publication HTML converted to text; optional article such as `86a`; 20,000-character excerpts with a cursor. |
| `check_legal_updates(since, offset=0, limit=100)` | One official ELI change page for all subjects; maximum limit 500. `since` uses `YYYY-MM-DDTHH:MM:SS` in the publisher's timezone-free format. |

Each successful ELI response has its exact URL, retrieval time, SHA-256 and
`validation_status=requires_review`. Empty, oversized, malformed and inconsistent responses
fail. Requests are bounded to `api.sejm.gov.pl` over HTTPS, without redirects, and never run
inside a unit of work. No taxpayer data is sent in these source requests.

A publication's text is not guaranteed to be consolidated for the transaction date. Metadata
`changeDate` is not a legal effective date. An empty article response may require reading the
full publication or another verified consolidation; it is not permission to reconstruct the
wording from model memory. A content hash proves which response was acquired, not that it is
the correct legal version. The response is not archived automatically.

## Validation and proposed monitoring

Follow [the legal-validation runbook](legal-validation.md). The tools acquire evidence; they
do not approve tax policy, schedule work, persist checkpoints or invalidate precedents.
The platform stores `legal_basis` as text; it does not yet enforce structured source evidence,
all validity periods, policy versions or legal freshness. The prompts disclose these limits.

Live connectivity, real Grok Bot role separation, vault transfer, Pages and routine triggers
remain external acceptance tasks. Passing local tests is not proof of any of them.

Official Grok Bot references: [overview](https://docs.x.ai/grok-bot/overview) and
[Pages](https://docs.x.ai/grok-bot/files-and-results#pages).
