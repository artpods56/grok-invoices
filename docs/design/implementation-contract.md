# Dashboard implementation contract

Target: `assets/design/dashboard-f-mockup.png`. Build the interactive inspection dashboard in `apps/web/` using React/Vite, Inter, and Phosphor regular icons. English UI. Synthetic demo only; no live KSeF, phone, or tax execution.

## Module boundaries

- UI shell owner: `apps/web/src/App.jsx`, `apps/web/src/styles.css`, `apps/web/index.html`. Own navigation, summaries, filters/search, selection, CSV export and overlays. Import domain and case details modules using the contract below.
- Domain owner: `apps/web/src/domain.js`, `apps/web/src/CaseDrawer.jsx`, `apps/web/src/case-drawer.css`, `apps/web/tests/domain.test.mjs`. Own fixtures, pure transitions, and case details UI. Do not edit App, global styles, package files, or the visual assets.
- Asset owner: `apps/web/public/assets/summary-completed.png`, `summary-waiting.png`, `summary-blocked.png`, and `docs/design/asset-provenance.md`. Use ImageGen for three pastel backgrounds with no text or icons; use source mock as reference. Supplied logo is copied by parent.
- Parent owns integration, build config, documentation, Outline and final browser QA.

## Domain API

`domain.js` exports `createDemoInvoices()` (fresh deep copy), `STATUS_LABELS`, `summarizeInvoices(invoices)` returning `{completed, waiting_for_client, blocked}`, `filterInvoices(invoices, {query, status})`, `exportInvoicesCsv(invoices)`, and `resolveDemoQuestion(invoices, invoiceId, answer)` returning a new invoices array. Reject incomplete answers and non-waiting cases; completed cases must not gain duplicate decisions. No real tax calculations.

Invoice fields: `id` (DEMO-001 through DEMO-004), `supplier`, `initials`, `date` (2026-11-05), `amount` (gross PLN), `netAmount`, `vatAmount`, `status` (completed/waiting_for_client/blocked), `context`, `question` (string or null), `answer` (object or null), `reasoning`, `sources` (array of `{title,url,note}`), `timeline` (array of `{time,title,description}`), `precedentId` (string or null).

Initial rows must match the mock: Demo IT Services / 615 / completed / IT services; Demo Fuel Station / 246 / completed / Known vehicle; Demo Fuel Station / 246 / waiting_for_client / Unknown vehicle; Demo Supplier / 123 / blocked / Missing context.

`CaseDrawer.jsx` exports named `CaseDrawer` with props `{invoice, onClose, onResolve}`. `invoice` can be null (render nothing). `onResolve(invoiceId, answer)` is called for a valid synthetic answer `{vehicleRegistration, usage, purpose}`; usage is `mixed` or `business`. Parent applies domain transition. Drawer must clearly label any demo-only mutation. Include invoice data, context question and reply form, sources, reasoning and timeline. Responsive and keyboard accessible. Its CSS uses class prefix `case-` and must not restyle the app globally.

Summary cards consume `/assets/summary-completed.png`, `/assets/summary-waiting.png`, `/assets/summary-blocked.png`. Use `/assets/logo-v2.png` for the current pastel folded-G brand mark. Keep whitespace and composition faithful, with responsive mobile navigation and horizontally scrollable table if needed.

Every worker is part of a team; never revert others' work. Commit only owned files with short English messages. Do not modify Outline or root shared documentation; the parent synchronizes them.
