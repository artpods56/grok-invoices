# Dashboard visual direction

Decision date: 2026-11-05.

## Selected reference

The project owner selected reference F, **Modern Invoicing Dashboard Management System** by Orbix Studio, and requested a faithful visual reproduction adapted to Grok Invoices.

- Original: https://dribbble.com/shots/27114868-Modern-Invoicing-Dashboard-Management-System
- Reference image: https://cdn.dribbble.com/userupload/46833070/file/62fb9381b31746c7eb554b407f62e35c.jpg

Preserve the light neutral canvas, narrow left sidebar, compact top bar, three pastel gradient summary cards, restrained typography, invoice table, spacing, and soft borders. Use English product copy and Grok Invoices branding. Do not introduce a dark agent graph or an unrelated visual direction.

## Product adaptation

The dashboard is a supporting inspection surface. The primary client interface remains Grok Bot.

- Summary cards: completed, waiting for client, and blocked cases.
- Invoice table: supplier, invoice identifier, date, gross amount, status, and case context.
- Hero case: a synthetic fuel invoice for an unknown vehicle, with net PLN 200.00, VAT PLN 46.00, and gross PLN 246.00.
- Case details should eventually expose the question, client answer, sources, decision, and precedent references.
- Mockup values are synthetic. Neither a status card nor a visual phone indicator establishes a working integration.

## Delivery status

- Inspiration research: completed; six references presented in the conversation.
- Visual direction: selected by the owner.
- Adapted mockup: generated with built-in ImageGen and visually inspected; see [dashboard-f-mockup.png](../../assets/design/dashboard-f-mockup.png).
- The image preserves the selected reference's visual direction, with Grok Invoices branding, English copy, and four synthetic invoice rows. It is an adaptation, not a verified pixel-exact reproduction.
- The mockup uses an additional blocked example to demonstrate all three statuses; it does not replace the regression scenario in the project context.
- Visual check: summary counts match the table (2 completed, 1 waiting for client, 1 blocked); the unknown-vehicle invoice is PLN 246.00. No external integration was exercised.
- Dashboard implementation and external integrations: not implemented by this design task.

## Working agreement

Commit coherent changes regularly. Keep the Outline project concept current with decisions, deliverables, verification limits, and commit references. Preserve authentic build history and never manufacture session exports.
