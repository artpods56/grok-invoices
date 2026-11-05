# Grok Invoices: project context

Snapshot: 2026-11-05. This is a readback of project planning, not evidence of a working product. Recommendations in the research reports are proposals unless explicitly adopted.

## Product direction

Grok Invoices is an Agents as a Service platform intended to handle accounting for founders in Poland from intake to completion. The long-term ambition is end-to-end correctness. The hackathon demonstrates a bounded invoice decision workflow; it does not establish complete accounting coverage or guaranteed legal correctness.

The current Outline concept selects the Multiplayer AI track, supported by multiple backend agents. The client collaborates through a personal Grok Bot. The platform owns company facts, invoices, questions, decisions, precedents, and the audit trail.

## Confirmed planning sources

- [Outline: project concept](https://outline.stackinghq.com/doc/agentowe-biuro-rachunkowe-koncepcja-projektu-I7dx93MlAu), revision 21, updated 2026-11-05 at 17:57:53 UTC.
- [Outline: fuel invoice phone demo](https://outline.stackinghq.com/doc/demo-telefon-po-fakturze-paliwowej-4iNXmYJhUH), revision 3, updated 2026-11-05 at 18:01:16 UTC. This narrows the live presentation to one phone-call scenario.
- [Online tldraw: Main](https://www.tldraw.com/f/KaR4fIEC8MqIEIAV68ENK), Hackathon workspace. Read through the browser after the tldraw connector's board view did not connect. It contains an early sketch of clients, bots, an accountant, an invoicing integration, and onboarding with a tax identifier and KSeF credential. It does not specify the detailed decision flow.
- [Other accessible online board](https://www.tldraw.com/f/6-UY22uYXJWLhSXRWy_ap): three unlabeled circles, with no additional written project decisions at inspection time.
- Two organizer slides supplied in this conversation: submission requirements and judging criteria, summarized below.

The more detailed, later Outline concept supersedes the early sketch where they differ. In particular, a human accountant is not a mandatory participant in the current demo. This is a planning readback, not a claim that the resulting system is ready for autonomous production accounting.

## Roles and boundaries

1. **Invoice agent:** imports purchase invoices from KSeF or synthetic demo data; stores them; handles supported simple cases; checks company-specific precedents; opens difficult cases for the regulatory agent.
2. **Regulatory agent:** checks applicable sources, company facts, and prior decisions; creates a context request when facts are missing; records a supported decision or an explicit block.
3. **Client agent:** a reusable Grok Bot template connected to a shared public HTTPS MCP server. It collects facts/documents, relays questions and answers, and presents results. It does not independently interpret law, book invoices, or maintain precedents.

Company scope is derived from the authorized MCP connection. A company identifier supplied in a tool argument is not authorization. KSeF credentials go through a secret-aware vault/tool flow rather than ordinary chat.

Minimal planned MCP tools: `start_onboarding`, `configure_ksef`, `submit_document`, `list_open_questions`, `answer_question`, and `get_status`.

The chat is the primary client interface. A Page presents results, sources, and refresh time. A minimal read-only dashboard supports inspection. The platform remains the source of truth; a Page is a refreshed projection.

## Decision and precedent contract

- Separate expense classification, company-specific accounting treatment, VAT treatment, and missing context.
- Decision statuses: `completed`, `waiting_for_client`, and `blocked`.
- Retain invoice/company identity, source references, context references, reasoning, plan-of-accounts/policy version, and any source precedent ID.
- An answered question is resolved only after its answer supplies sufficient facts. Repeated delivery must not create another decision.
- A precedent requires matching facts, company scope, policy versions, source validity, and application conditions. The same supplier or similar text is insufficient.
- A changed vehicle fact, accounting policy, or legal basis triggers reassessment. Blocked cases do not become automatically reusable precedents.

## Current presentation scenario

The broader regression story has four invoices: a simple IT service, fuel matching an existing vehicle precedent, fuel for an unknown vehicle, and a later invoice reusing the newly established context.

The newer live demo concentrates on the unknown vehicle:

1. Issue a synthetic purchase invoice in KSeF TEST from a prepared seller profile to the dedicated test buyer.
2. Confirm buyer-side permanent storage and obtain the KSeF number. Seller-side acceptance alone is insufficient for the planned trigger.
3. Download the invoice XML. The project notes say metadata alone does not provide the line details/registration needed for the question; verify this in the actual integration.
4. Extract the registration and check it against the fleet. Do not match a fuel precedent on supplier alone.
5. Create a linked question. The agent calls the client to ask which vehicle the purchase concerns and how it is used.
6. Save the answer, reevaluate the case, and record the outcome with evidence and conditions for subsequent reuse.

The prepared invoice has net PLN 200.00, VAT PLN 46.00, and gross PLN 246.00. These are synthetic fixture amounts from the planning document, not a verified taxpayer result. Invoice VAT rate and deductible VAT share are separate concepts. The call has not been placed or tested in this research task.

## Open decisions and prerequisites

- Choose the first supported company/tax regime. A sole trader's records and a company's full accounting are different products; a generic founder profile is insufficient.
- Confirm the test buyer identity/profile, presentation phone number, and fleet fixture without the unknown vehicle.
- Verify how a platform question proactively starts the Grok Bot/phone call. `list_open_questions` is a read, not push delivery. A manually triggered active conversation is a fallback, not proof of autonomous notification.
- Verify vault-to-MCP secret handling and the actual public HTTPS integration.
- Verify Page creation/refresh behavior end to end.
- Define who validates newly generated legal rules and how unsupported/conflicting interpretations are handled. The current plan blocks unresolved cases and does not require an accountant to approve every demo transaction.
- Keep automated completion coverage separate from correctness. A blocked case is not successful end-to-end completion, even when blocking is the correct behavior.

## Hackathon scope and submission

The concept scopes in platform state, the three roles, linked questions/answers, conditional precedents, synthetic fixtures, one results Page, and minimal inspection UI. Live KSeF TEST import and online legal research are stretch integrations in the concept; the newer demo aspires to use TEST import. Authentication UI, concurrent multi-client support, and full books are outside that MVP.

Organizer slides require a private code repository with judges invited, authentic AI coding session exports in `/sessions` at repository root, and preserved commit/build history. Ideas may predate the event, but implementation must happen during the sprint; libraries and open-source forks remain allowed subject to the preceding rules slide, which was not provided.

Five judging criteria are scored 1-5 each: working end-to-end prototype; technical complexity and integration; innovation and creativity; real-world impact; and alignment with people plus AI or multiple agents working toward a shared goal.

At initial inspection, HEAD was `6c0e3ec` (`Initial commit`), the worktree was clean, and tracked files were only `README.md` and `assets/icon.svg`. No application, legal watcher, test suite, dataset, or session export existed in this checkout. This task adds research/documentation only.
