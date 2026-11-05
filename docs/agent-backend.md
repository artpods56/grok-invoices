# Agent backend

The platform is the agents' office: one FastAPI/SQLite store, three dedicated FastMCP
servers, fixed actors per role and shared service/domain rules. It never calls a model.
Grok Bots perform reasoning outside the backend. The invoice document is ksef2's native
FA(3) model, not another invoice schema.

- [Grok Bot setup, endpoints and prompts](grok-bot-setup.md)
- [Legal evidence, freshness and proposed monitoring](legal-validation.md)
- [Platform architecture and commands](../AGENTS.md)

## Implemented and locally verifiable

- Invoice ingestion, account checks, conditional vehicle precedent matching, posting,
  escalation, question/answer relay, vehicle facts and decision history.
- Dedicated invoice, regulations and client MCP servers with separate invite checks.
- Same unanswered question retries return the existing question. Identical answer retries
  return the stored answer, including after case resolution, without duplicate events.
  Changed answers are rejected. Answers resume analysis; they do not book an invoice.
- Precedent reuse must retain the source decision's account and deduction, including when
  invoked through REST rather than the MCP wrapper.
- Read-only ELI title search, act metadata/references, text acquisition and paged change
  discovery. Successful acquisition stays requires_review and does not activate a tax rule.
- Local three-role MCP transport smoke on a temporary database:
  uv run python -m scripts.smoke_agents.

## Evidence boundaries

Fixtures and synthetic tax examples are a bounded demo. search_regulations is explicitly
non-authoritative. The server does not enforce all planned policy versions, validity dates
or legal-freshness conditions. legal_basis stores text, not an independently validated
evidence graph. decide currently creates a reusable precedent, so unsupported reuse scope
must remain blocked.

ELI reads do not install a watcher, archive source bodies, persist checkpoints or invalidate
precedents. Grok Bot connectivity, private vault transfer, Pages and automatic wake-up need
external acceptance. An MCP protocol smoke does not demonstrate a running Grok Bot swarm.
Live KSeF tests are separate and excluded from the default pytest command.

Earlier /api/agents/run, setup-demo and generic /mcp descriptions belonged to a superseded
implementation. They are not endpoints in the current platform. Use the role-specific
/agents/{invoices,regulations,client}/mcp endpoints and explicit Grok Bot turns.
