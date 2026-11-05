# Legal evidence and freshness runbook

This is an operating procedure for the Regulations Agent, not a legal opinion or a guarantee
of universal correctness. Evidence acquisition tools are implemented. Scheduled monitoring,
a versioned rule registry and automatic precedent invalidation are proposals.

## Sources and authority

| Source | Use | Do not infer |
| --- | --- | --- |
| [ELI / Dziennik Ustaw](https://api.sejm.gov.pl/eli/openapi/) | Enacted acts, publications, references and amendment discovery. | A recent metadata update means an article applies today. |
| [MF / KIS EUREKA](https://podatki.gov.pl/narzedzia/eureka) | Official interpretations, binding information and factual context. | Another taxpayer's interpretation gives blanket protection. No stable bulk API was verified. |
| [MF KSR](https://www.gov.pl/web/finanse/krajowe-standardy-rachunkowosci) | National accounting standards, exact attachment/version. | Every accounting standard is a tax deduction rule. |
| [ZUS](https://www.zus.pl/kanal-rss) | Contribution notices and official change discovery. | An RSS item alone establishes an applicable calculation. |
| [KSeF integrator documentation](https://ksef.podatki.gov.pl/ksef-na-okres-obligatoryjny/wsparcie-dla-integratorow/) | Interface versions, schemas and technical deadlines. | API acceptance certifies a tax treatment. |
| [EUR-Lex](https://eur-lex.europa.eu/) | Relevant EU legislation and version history. | A secondary summary replaces applicable national/EU provisions. |
| RCL / Sejm legislative process | Early warning about proposed changes. | A bill is enacted or already effective law. |

Only ELI has new live MCP acquisition tools here. Other links are research/manual sources,
not implemented connectors. Existing research explains additional scope and limitations:
[accounting](research/polish-accounting-and-sources.md),
[AI regulatory knowledge](research/ai-regulatory-knowledge.md),
[source access probes](research/source-checks.md).

## Per-decision procedure

1. Establish taxpayer, transaction and tax period, company policy, taxable business purpose,
   relevant vehicle/use and supporting documents. Do not infer these from a seller match.
2. Find the act, read its metadata and references, identify the publication or consolidated
   text and its legal-status date. Follow later amendments, implementing provisions,
   commencement and transitional rules. Preserve the original Polish wording as evidence;
   an English explanation is a separate paraphrase.
3. Read the relevant provision and all relevant exceptions. Drain text excerpt cursors.
   If an article route is empty, try the full verified publication or a verified alternative.
   Leave the case blocked if the required evidence cannot be acquired.
4. Distinguish publication, commencement, application period, transaction date, consolidation
   date, publisher metadata change and retrieval time. None is a substitute for another.
5. Check supporting official interpretations where relevant and record their factual limits.
6. Test the proposed account against the company's chart and deduction against actual facts.
   A company-use declaration alone is insufficient evidence for every 100% vehicle deduction.
7. Before `decide`, put a compact evidence record in `legal_basis` and reasoning in `rationale`.
   If the current conditions model cannot safely bound reuse, leave the case open rather than
   creating a broadly reusable precedent. A high confidence score cannot clear a blocker.

Suggested text record, filled only with observed evidence:

```text
Mode: LIVE_RESEARCH or SYNTHETIC_DEMO
Question and transaction period: ...
Provision and publication ELI: ...
Official source URL: ...
Retrieved at and SHA-256: ...
Publication / consolidation legal-status date: ...
Effective and applicable period, including transitions: ...
Later amendments checked and their effect: ...
Client facts, documents and question IDs: ...
Account and client policy reference: ...
Exceptions considered and remaining blockers: ...
Precedent scope and reassessment conditions: ...
```

Missing fields are unresolved work, never values to invent. This is a convention inside a
free-text field, not a server-verified legal-evidence schema or immutable source archive.

## Change scan procedure

On an explicitly requested run, call `check_legal_updates` from a conservative known baseline.
For a first run without a trustworthy checkpoint, state the chosen baseline and its historical
coverage limit. Retrieve every page from offset 0 with the same `since` and filters. Persist
no new checkpoint after failures, inconsistent pages, gaps or unreviewed relevant updates.
The tool itself persists nothing. `coverage_complete=false` on a later page does not become
true merely because that page is last: the operator must account for all earlier pages.

The feed changes during paging. Overlap the next scan, deduplicate using publication identity
and `changeDate`, and reconcile watched acts directly. A feed change may concern metadata
on an old act. Compare the relevant wording and application dates before concluding that a
tax rule changed. An unchanged hash does not prove the dependency graph was checked.

For an affected rule, identify open cases and existing precedents, report them for reassessment
and stop automatic reuse where freshness cannot be established. The current platform has no
general legal-change invalidation endpoint; do not claim the MCP has disabled a precedent.
An accountant correction can supersede a posting, but should not be invented as an automated
rule update. A durable versioned policy/invalidation service is future work.

Proposed routine: daily discovery scans, source checks before each live decision, a full
reconciliation before month close/filing and immediate review of relevant published changes.
These are proposed operating targets, not installed timers or an SLA. Grok Bot routine
support, trigger delivery and checkpoint storage must be demonstrated before relying on them.

## Evidence thresholds

| Situation | Action |
| --- | --- |
| Official text, dates, facts and exclusions verified | Explain the result and record evidence; only decide within supported scope. |
| Missing taxpayer/vehicle/purpose information | Ask the client once, using the existing case and question IDs. |
| Source unavailable, empty, partial, conflicting or beyond reviewed coverage | Keep the case open; report BLOCKED, the exact evidence gap and next step. |
| Synthetic demo reference only | Label every outcome SYNTHETIC DEMO; do not present it as validated current law. |
| New interpretation or amendment discovered | Review application dates and affected decisions before approving a policy change. |

Measure errors among completed decisions, automation coverage, blockers and unresolved cases
separately. A blocked case is not a successful posting; source retrieval success is not tax
correctness. The hackathon demo does not demonstrate complete Polish bookkeeping, statutory
filing, payments, payroll or universal 100% accuracy.
