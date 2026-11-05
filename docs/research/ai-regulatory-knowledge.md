# Regulatory knowledge for an AI accounting agent

Research date: 2026-11-05. Status: technical research and proposed design, not an implemented integration or a statement that any tax treatment has been legally validated.

## Recommendation

Build a small, versioned evidence service behind the regulatory agent. Let Grok identify relevant provisions, ask for missing company facts, and explain results. Let application code select eligible rule versions, verify evidence, calculate amounts, and enforce completion conditions. Web search discovers sources; a retrieved paragraph or agreement between agents does not establish that all applicable law was considered.

The hackathon should demonstrate one bounded workflow with traceable evidence and explicit blocking. Production coverage of all Polish accounting, taxes, filings, and exceptional cases is a separate undertaking. A system that blocks every case can avoid incorrect automatic postings while providing no useful automation, so correctness and coverage must be measured separately.

## 1. Sources that machines can actually consume

The official ELI OpenAPI specification documents a changes endpoint with `since`, `offset`, and `limit`, a default limit of 100 and maximum of 500, act metadata, references, structure, and HTML/PDF retrieval. It is an acquisition interface, not a legal reasoning engine. [ELI OpenAPI](https://api.sejm.gov.pl/eli/openapi/)

A live read during this research confirmed that the VAT act metadata endpoint responds and exposes references to amendments and consolidated publications. The changes request below returned `{count: 2, offset: 0, totalCount: 124, items: [...]}`. These counts are a point-in-time observation, not an expected fixture:

```text
GET https://api.sejm.gov.pl/eli/acts/DU/2004/535
GET https://api.sejm.gov.pl/eli/changes/acts?since=2026-11-04T00%3A00%3A00&limit=2&offset=0
```

The parent investigation also observed HTTP 200 with an empty body from a requested VAT article fragment. Treat this as failed content acquisition, not evidence that the provision is absent or verified. Test bytes, content type, expected document identity, and parse completeness before indexing.

Other acquisition channels have different contracts:

- EUREKA officially supports searching interpretations and binding information by document type, phrase, reference, and date. This research did not establish a supported, documented bulk-ingestion API. Preserve a manual or browser-assisted acquisition path until its automation contract is verified. [Ministry of Finance: EUREKA](https://podatki.gov.pl/narzedzia/eureka)
- ZUS publishes RSS feeds; the parent investigation confirmed a live XML response for its news feed. Use feeds as discovery signals and retrieve the underlying document. [ZUS RSS](https://www.zus.pl/kanal-rss)
- Keep official accounting standards, Ministry explanations, technical KSeF contracts, and draft legislation in distinct source classes. They answer different questions and must not be assigned identical legal authority. The broader source registry belongs in the companion accounting report.

## 2. Dates and legal versions are the critical design issue

An official ELI identifier distinguishes published, consolidated, and editorially updated representations. The Sejm explicitly describes the editorially updated representation as lacking legal force. A convenient up-to-date text therefore remains linked to the promulgated sources that justify its wording. [Sejm: ELI identifiers and text representations](https://eli.sejm.gov.pl/)

Proposed evidence records should retain:

- `source_id`, issuing authority, document class, canonical URL, original bytes, and content hash;
- publication date, source update timestamp, retrieval timestamp, parser/version, and acquisition outcome;
- act, article, paragraph, item, letter, annex, page, and bounding box where available;
- entry into force, application period, transition conditions, and supporting amendment references;
- status such as `unprocessed`, `verified`, `superseded`, `incomplete`, or `conflicting`.

Do not equate source `changeDate`, retrieval time, publication, and legal applicability. Likewise, an invoice has several dates: issuance, receipt, supply, payment, and the relevant accounting/tax period. Which date controls a decision is itself part of the rule. Preserve effective intervals at provision level and attach transition predicates instead of assuming the act's single entry-into-force field settles every paragraph.

A concrete example: the 2026 VAT consolidation was published on 2026-09-28 but identifies its legal-status date as 2026-08-26. Its publication alone therefore cannot prove coverage of all law relevant on 2026-11-05; later amendments still require checking. [VAT consolidation metadata](https://eli.gov.pl/eli/DU/2026/1263/ogl)

Maintain two timelines: when the rule applies and when the platform learned it. This permits reproducing both a historical decision and a corrected decision made after discovering new evidence. Never overwrite the old basis silently.

This is supported by original legal-RAG research showing that genuine citations can still refer to the wrong temporal version. The cited benchmark concerns French tax law; its findings motivate Polish temporal tests but do not validate this product. [Temporal Misgrounding in Legal RAG](https://arxiv.org/abs/2608.09393)

## 3. Read structure before asking a model to interpret text

Prefer available structured HTML or native PDF text. For scans or broken text layers, use layout-aware extraction with explicitly configured Polish OCR and retain the page image for verification. Docling supplies layout/table processing, OCR options, and structure-aware chunking; these are useful building blocks, not a guarantee of Polish legal accuracy. [Docling technical report](https://arxiv.org/abs/2408.09869), [OCR documentation](https://docling-project.github.io/docling/concepts/OCR/)

Proposed conversion checks:

1. Detect empty output, missing pages, replacement characters, damaged numbering, and implausible differences between native text and OCR.
2. Preserve negation, percentages, decimal separators, dates, enumerations, footnotes, and table headers. A dropped exception can reverse the conclusion.
3. Split by article and subordinate legal units. Carry headings and parent definitions into retrieval context; expand cross-references deliberately.
4. Preserve annex/table coordinates and repeated headers when splitting large tables. Never let a row lose its threshold units or applicability header.
5. Store Polish source text as evidence; English descriptions are supplementary, not an authoritative replacement. Repository documentation remains English; source artifacts can live in the evidence store.

Docling's hybrid chunker refines document hierarchy using token limits and supports repeated table headers. Its generic output still needs a legal-structure adapter and validation. [Docling chunking](https://docling-project.github.io/docling/concepts/chunking/)

Do not solve this by putting every act in one giant prompt. Original long-context research demonstrates sensitivity to where relevant material appears. Use focused evidence packs and evaluate retrieval separately from reasoning. [Lost in the Middle](https://arxiv.org/abs/2307.03172)

## 4. Retrieve evidence with eligibility filters

Proposed retrieval sequence:

1. Build a structured question from the accounting issue, transaction dates, taxpayer type, registration status, and missing facts.
2. Filter by jurisdiction, source class, applicable period, and rule status before ranking. Keep historical versions when the question concerns an older period.
3. Combine lexical retrieval for exact article numbers and technical terms with semantic retrieval for client language. Rerank the candidate set and include referenced definitions, exceptions, and transitions.
4. Return an evidence pack with immutable source IDs, exact spans, version dates, and an explicit list of unresolved dependencies.
5. Validate that every consequential claim cites an actual retrieved span and that the span supports the claim. Link existence is insufficient.

These are design recommendations, not claims that a particular retriever has already achieved an accuracy level. Start with lexical lookup plus explicit provision IDs for the demo; add embeddings only if evaluation shows a retrieval problem.

xAI's documented `web_search` supports real-time search and an `allowed_domains` filter with up to five domains. Use separate queries for coherent official-source groups. Allowlisting reduces source noise but does not prove completeness, legal applicability, or freedom from hostile content. The SDK and Responses API use different parameter shapes; follow the selected SDK's actual schema. [xAI Web Search](https://docs.x.ai/developers/tools/web-search)

## 5. Give the agent narrow tools and enforce decisions on the server

Proposed internal tools:

```text
search_legal_sources(question, issue_tags, relevant_dates)
get_legal_evidence(source_id, provision_path, version_id)
get_company_facts(case_id)
request_company_context(case_id, missing_fields)
evaluate_accounting_rule(case_id, rule_version_id)
record_decision(case_id, evidence_ids, expected_case_version)
```

Bind the company to authenticated server context. Do not grant access merely because a model supplies a different `company_id`. Client facts need scope and provenance: a statement about one vehicle does not update the whole fleet. Validate answers against a schema and keep unresolved contradictions visible.

xAI documents remote MCP over supported HTTP transports and selective tool exposure using `allowed_tools` or the native SDK's `allowed_tool_names`. An empty list allows all, so configure a real allowlist. This documents an API capability, not proof that the hackathon's Grok Bot has all required features enabled. [xAI Remote MCP](https://docs.x.ai/developers/tools/remote-mcp)

The regulatory model proposes rule selection and explains why conditions apply. Application code validates those conditions and calculates money with decimal arithmetic and explicit, rule-specific rounding. Decimal arithmetic avoids binary representation errors; it cannot decide which tax rounding rule applies. [Python decimal documentation](https://docs.python.org/3/library/decimal.html)

Completion requires verified applicable evidence, sufficient company facts, supported treatment, validated arithmetic, and consistent case state. Otherwise persist `waiting_for_client` or `blocked` with a precise reason. An independent model can help detect omissions, but agreement is not a legal proof. Domain validation of production rule packs is advisable without making a human approve every demo transaction.

## 6. Update dependencies, not just the search index

Proposed update workflow:

```text
source change -> immutable snapshot -> structural diff -> affected provisions
-> candidate rule changes -> validation -> activated rule version
-> affected precedents and cases -> targeted re-evaluation
```

An ingestion checkpoint advances only after the entire batch is durably stored. Read every page; deduplicate by source identity plus version/hash. Use an overlapping `since` window, retries with backoff, and periodic inventory reconciliation. Do not assume pagination provides snapshot isolation or timestamps specify a timezone when the contract does not say so. Record upstream timestamps without silently reinterpreting them as UTC.

Maintain dependencies from provision versions to rules, precedents, and decisions. Mark affected precedents ineligible for new automatic use while a material change is unresolved. Route previously posted items to a correction workflow; never rewrite a closed ledger merely because a new document arrived. Unrelated rules can continue if their evidence remains valid.

Proposed initial operating targets are polling ELI every 30 minutes, daily reconciliation of the selected source inventory, and an explicit freshness check before finalizing a case. These are configurable engineering targets, not official publication-latency guarantees. Measure the lag from source availability to validated activation. A source outage, incomplete parse, or unreviewed relevant amendment must produce a visible degraded state. Cached evidence can support decisions only under an explicit freshness policy; otherwise block the affected issue.

## 7. Treat retrieved documents as data

Downloaded pages, PDF text, invoices, and MCP results can contain instructions directed at the model. They must never grant access, alter system policy, activate rules, or authorize filing. Keep the research component read-only, validate tool parameters, restrict egress, sanitize rendered content, and separate evidence from trusted instructions. The server must enforce these boundaries even when a model follows hostile text. [OWASP MCP security guidance](https://cheatsheetseries.owasp.org/cheatsheets/MCP_Security_Cheat_Sheet.html)

Do not pass company secrets into public search queries. Keep downstream credentials outside model-visible legal evidence, validate authorization audiences, and apply least privilege. MCP security guidance specifically rejects unvalidated token passthrough. [MCP security best practices](https://modelcontextprotocol.io/docs/draft/tutorials/security/security_best_practices)

## 8. Hackathon implementation and production progression

For the hackathon, implement a small curated source pack for the fuel-invoice case, a source manifest with hashes/dates, one verified rule, typed company facts, and the existing question/answer workflow. Show the exact provision and company evidence used, plus an intentionally blocked variant. An optional read-only change check can demonstrate freshness without pretending an arbitrary legal amendment has been automatically understood.

Next, add provision-level history, resilient ingestion, a rule-change queue, dependency invalidation, and a reviewed regression corpus. Production adds complete persona-specific obligations, document retention, operational monitoring, correction procedures, and validated filing integrations. More agent roles do not replace these controls.

Evaluate at least:

- legal-source retrieval recall and correct version selection;
- citation support and extraction fidelity for numbers, negation, and tables;
- correctness of completed decisions and unsafe-completion rate;
- automation coverage and time spent waiting or blocked;
- missed-change rate, freshness lag, and precedent invalidation;
- reproducibility, idempotency, and tenant isolation.

Include cases immediately before and after a change, transitions, foreign/inapplicable interpretations, missing vehicle facts, changed company policy, duplicated answers, source outages, empty HTTP 200 bodies, and injected instructions. Ground truth needs qualified accounting review; an LLM judge alone is insufficient for monetary and temporal correctness. No finite test suite establishes universal 100% accuracy, and blocking a case must not count as successfully completing its bookkeeping.
