# Client-first README illustrations

The README leads with the company owner's Grok Bot experience: provide company context,
answer an invoice-specific question, then request progress. The dashboard is a supporting
view. Three role-specific Grok Bots use the same platform for accounting state.

## Sources read on 2026-11-05

- [Project concept, revision 49](https://outline.stackinghq.com/doc/grok-invoices-koncepcja-projektu-I7dx93MlAu): personal assistant as the primary client interface; company documents, questions, answers and requested Pages.
- [Grok Bot setup, revision 5](https://outline.stackinghq.com/doc/grok-bot-setup-prompts-and-mcp-Bf7mRPwe1F): six client tools, private vault handling, explicit bot passes, status counts and Pages limitations.
- [Technical documentation, revision 80](https://outline.stackinghq.com/doc/dokumentacja-techniczna-zIvV4QQqT5): implemented MCP servers, shared company, TEST-only intake, public dashboard and outstanding external acceptance.
- Current `apps/api/client-agent-template.md`: the assistant collects and relays facts; it does not decide accounts or VAT. Its status tool supplies counts and onboarding state, not detailed legal rationales.

The technical document takes precedence over earlier product proposals when describing
implemented behavior. A platform case reopening is distinct from a Grok Bot waking up.

## Assets

| Asset | Purpose |
| --- | --- |
| `assets/readme/hero.{svg,png}` | Current logo and client-facing product introduction. |
| `assets/readme/client-experience.{svg,png}` | Three client steps and an illustrative question/answer about the unfamiliar `GD 9R247` vehicle. |
| `assets/readme/grok-bot-team.{svg,png}` | Client Assistant, Invoice Agent and Regulations Agent, each with a bidirectional MCP connection to the shared platform. |
| `assets/readme/visuals.html` | Self-contained gallery for local review. |

The pastel rims, light panels, restrained type and current logo follow the dashboard.
The SVGs are editable; the README embeds PNGs for consistent GitHub rendering. The logo
is resized from the canonical `apps/web/public/assets/icon.svg` without changing its design.

Recreate all outputs after installing the existing web dependencies:

```sh
node scripts/render_readme.mjs
```

The script uses the web app's existing Sharp dependency and adds no package.

## Evidence and limits

These are authored vector diagrams, not live Grok Bot screenshots or evidence of an
external integration. The English conversation translates the Polish stage narrative.
The Skoda/client-delivery answer is synthetic illustration copy, not a reported client fact.
The assistant confirms that an answer was recorded for review, not that an invoice was booked.

Pages are described conditionally and on request. Actual bot connections, private
vault-to-tool transfer, Pages and automatic refresh still require external acceptance.
No automatic cross-bot wake-up, multi-tenant isolation or live Polish phone call is claimed.

Verification: inspected the rendered PNGs and a combined HTML preview, checked text and
roles against the cited Outline documents, and reviewed Git whitespace checks. No
application tests or builds were run, following the owner's earlier instruction.
