# Polish accounting workflow and official legal sources

Research date: 2026-11-05. This is a domain research report and a proposed product scope, not an implemented accounting service or a complete legal opinion. Sources were checked online during this research; their publication dates and applicability still need to be recorded for each production decision.

## 1. Start with the taxpayer, not the invoice

There is no single bookkeeping workflow for every Polish founder:

| Customer profile | Core records | Product consequence |
| --- | --- | --- |
| Sole proprietor (JDG), progressive or flat-rate income tax | Usually a tax revenue-and-expense ledger (KPiR), unless accounting books apply | Recognize income and deductible costs, fixed assets and applicable adjustments; do not invent a general-ledger account requirement |
| Eligible sole proprietor using tax on registered revenue | Revenue register and fixed-asset records | Purchase classification does not automatically reduce the income-tax base |
| Limited liability company or another entity within the Accounting Act | Accounting books, accounting policy and financial statements | Account assignment must use the entity's chart of accounts and accounting policy |

The Ministry's [business-start guide](https://podatki.gov.pl/poradniki-i-informatory/rozpoczecie-dzialalnosci-gospodarczej) and [flat income-tax guidance](https://podatki.gov.pl/podatki-firmowe/pit/informacje-podstawowe/co-jest-opodatkowane/opodatkowanie-podatkiem-liniowym) identify KPiR or accounting books. Its [registered-revenue-tax guidance](https://podatki.gov.pl/podatki-firmowe/pit/informacje-podstawowe/co-jest-opodatkowane/opodatkowanie-ryczaltem-od-przychodow-ewidencjonowanych) identifies the revenue register and asset records. Eligibility, elections and exceptions must be checked separately.

The [Accounting Act, official consolidated working text](https://eli.gov.pl/api/acts/DU/2026/522/text/U/D20260522Lj.pdf), covers commercial companies with stated exceptions and revenue conditions for certain natural-person entities (Article 2). It requires a written accounting-policy framework (Article 10), double-entry general-ledger recording (Article 15), and source evidence for accounting entries (Article 20). Management retains statutory accounting responsibility, including supervision when work is entrusted to another party (Article 4(5)). An AI service therefore does not erase the company's legal responsibilities.

VAT status is an independent dimension. Store it separately from legal form and income-tax regime.

## 2. What an end-to-end service actually has to complete

The following is a proposed operational decomposition. A working invoice classifier completes only part of it.

1. **Establish the mandate and company profile.** Identify the company, tax regimes, reporting periods, start date, opening balances or prior records, assets, vehicles, employees, foreign transactions, exemptions, and existing elections. Record who supplied each fact and when it becomes effective. Verify permissions for each external system. KSeF access is not tax-filing authority: the Ministry distinguishes general representation from the separate UPL-1 authorization for electronic tax declarations. See [current authorization guidance](https://podatki.gov.pl/potrzebuje-pelnomocnictwa).
2. **Collect the complete evidence.** Receive purchase and sales invoices, corrections, relevant bank/payment data, contracts and supporting documents. Track expected-but-missing evidence. KSeF has exclusions, including particular transport tickets, insurance-related invoices with reduced data, and foreign-supplier situations; it is not the complete accounting record. See [official KSeF scope](https://ksef.podatki.gov.pl/informacje-ogolne-ksef-20/zakres-obowiazkowego-ksef/).
3. **Validate and deduplicate.** Verify identity, currency, arithmetic, document references, correction relationships and duplicate imports. Preserve original documents. A PDF representation and a KSeF XML may describe the same event. Successful KSeF ingestion does not prove business purpose or tax deductibility.
4. **Resolve the accounting and tax questions separately.** Decide the accounting category and recognition period, income-tax treatment, and VAT treatment. Ask a specific question when evidence is insufficient. Keep a vehicle-specific answer scoped to that vehicle and period.
5. **Maintain records and reconcile.** Post to the appropriate register or books; reconcile payments, bank balances, receivables/payables and applicable asset records. Investigate mismatches and missing sales or expenses. For full accounting, balance-sheet and closing work goes beyond coding purchase invoices.
6. **Calculate obligations and produce filings.** Determine applicable PIT/CIT advances, VAT reporting, social/health-insurance settlement and annual obligations. Generate the right schema for the taxpayer and period, validate it, sign through an authorized mechanism and obtain the official acknowledgment. A generated XML, successful HTTP request and accepted filing are different states.
7. **Communicate and verify payments.** Explain what is due, its period, destination and deadline. Distinguish a payment instruction from evidence of settlement. Missing client authorization or a failed external submission must remain visible.
8. **Correct and preserve history.** Link revised evidence to earlier decisions, identify affected periods/filings, apply the appropriate correction process, and retain the previous version and reason. Do not silently overwrite a previously completed case.

### Three decisions that must not collapse into one

- **Accounting recognition:** which record/account and period are appropriate under the entity's framework?
- **Income-tax deductibility:** is there a documented connection to earning, preserving or securing revenue, and does an exclusion apply? The Ministry's [classic CIT guidance](https://podatki.gov.pl/podatki-firmowe/cit/cit-klasyczny/informacje-podstawowe-cit-klasyczny) lists multiple conditions and distinguishes direct and indirect cost timing.
- **Input VAT deduction:** does the purchase support taxable activities, and do timing restrictions or exceptions apply? The [VAT deduction guide](https://podatki.gov.pl/podatki-firmowe/vat/poradniki-i-informatory/odliczenie-i-zwrot-podatku-vat) describes those conditions separately.

An invoice addressed to a company settles none of these questions by itself. A confident expense label is insufficient to mark the case complete.

## 3. Current reporting facts that affect architecture

**VAT:** registered active VAT taxpayers generally submit JPK_VAT with declaration. Monthly filing is due by the 25th of the following month, with the stated non-working-day adjustment. Quarterly VAT settlement still involves monthly record submissions; the quarter-end submission includes the declaration component. See [MF guidance, updated 2026-10-13](https://podatki.gov.pl/podatki-firmowe/jednolity-plik-kontrolny/jpk_vat-z-deklaracja/jpk_vat-z-deklaracja). Do not derive quarterly behavior simply by running a monthly job every three months.

**Income-tax records:** MF's [JPK income-tax schema page](https://www.gov.pl/web/kas/struktury-jpk-w-podatkach-dochodowych) identifies JPK_KR_PD, JPK_ST_KR, JPK_PKPIR, JPK_EWP and JPK_ST. Its current rollout description starts KPiR/revenue-register cohorts obliged to JPK_V7M in 2026, and remaining PIT/registered-revenue-tax cohorts, including JPK_V7K, in 2027. Schema availability, the obligation to keep electronic records, the reporting year and the submission deadline must be represented separately. This research does not implement the complete rollout or exceptions.

**Social insurance:** payment and reporting obligations depend on payer status. ZUS currently gives the 15th of the following month for legal-person payers and the 20th for other payers, with non-working-day adjustment. Contribution amounts and health-insurance calculations require additional taxpayer facts and current rules; they are not a single universal percentage. See [ZUS payment instructions](https://www.zus.pl/firmy/rozliczenia-z-zus/opis-spraw/-/asset_publisher/nFNACg8jSsOg/content/id/10637176).

**Annual close:** accounting-book entities also face financial-statement preparation, signatures, approval and filing. See the government's [financial-statement guide](https://biznes.gov.pl/pl/portal/00245). Supporting this is a separate product capability from purchase-invoice processing.

## 4. Official source registry and applicability rules

This is a functional source map, not a claim that every item has equal legal force.

| Source | What to use it for | Applicability check |
| --- | --- | --- |
| [Journal of Laws](https://dziennikustaw.gov.pl/DU), [ELI metadata/API](https://api.sejm.gov.pl/eli_pl.html) | Published statutes, regulations, amendments and references | Read commencement and transitional provisions; record the relevant legal version |
| [Accounting Act record](https://eli.gov.pl/eli/DU/1994/591/ogl) | Accounting obligations and source links | Resolve applicable amendments, entity scope and reporting year |
| [MF Accounting Standards Committee](https://www.gov.pl/web/finanse/komitet-standardow-rachunkowosci), [standards](https://www.gov.pl/web/finanse/krajowe-standardy-rachunkowosci), [MF official journal](https://www.gov.pl/web/finanse/du-mffipr) | National accounting standards, positions and published instruments | KSR can be used for matters unregulated by the Act under Article 10(3); check the entity's adopted policy and standard version |
| [MF EUREKA](https://podatki.gov.pl/narzedzia/eureka) | General/individual interpretations, explanations and binding-information documents | Identify document type, date, status, facts and relevant provisions |
| [MF WIS guidance](https://podatki.gov.pl/wiazace-informacje-podatkowe-i-celne/wiazaca-informacja-stawkowa-wis/najwazniejsze-informacje-o-wniosku) | VAT classification/rate decisions | Match the goods/service, validity and statutory protection conditions |
| [ZUS RSS](https://www.zus.pl/kanal-rss) and current ZUS guidance | Insurance changes, operational explanations and technical notices | Match payer/insured-person category and effective period; retain statutory basis |
| [KSeF integrator documentation](https://ksef.podatki.gov.pl/ksef-na-okres-obligatoryjny/wsparcie-dla-integratorow/) and MF JPK schemas | Interface/schema changes and operational procedures | Version by environment, schema and reporting period; technical acceptance is not substantive tax approval |
| [EUR-Lex](https://eur-lex.europa.eu/homepage.html?locale=en), [EU Court](https://infocuria.curia.europa.eu/), [Polish administrative judgments](https://orzeczenia.nsa.gov.pl/cbo/query) | Relevant EU law and judicial interpretation | Identify the actual instrument/judgment, status, scope and relationship to domestic provisions |
| [Government legislative process](https://legislacja.gov.pl/) and parliamentary materials | Early warning about proposals | Keep proposals distinct from promulgated, applicable law |

An individual interpretation addresses the presented individual facts; do not promise another taxpayer the addressee's protection merely because a similar result was found. See [MF application guidance](https://podatki.gov.pl/interpretacje-podatkowe/najwazniejsze-informacje-o-wniosku). WIS needs different handling: MF explicitly describes conditional protection for other persons using published WIS for goods/services of identical character. Therefore a blanket rule that all third-party rulings are unusable or unprotective would also be wrong.

General interpretations, formal tax explanations and ordinary informational articles must have different source types. Commercial commentary can help discover an issue, but the decision should link back to the actual official instrument and relevant conditions.

ELI API live metadata checks returned `IN_FORCE` for base Accounting, PIT, CIT, VAT and Tax Ordinance acts. Their latest listed consolidated notices were respectively `DU/2026/522`, `DU/2026/592`, `DU/2026/554`, `DU/2026/1263`, and `DU/2026/622`. These are discovery observations, not certification that a single downloaded consolidation contains all law applicable to every date.

## 5. Recommended first persona and acceptance contract

**Proposal:** begin with one Polish JDG providing domestic B2B services, using KPiR, active monthly VAT, PLN transactions, no employees, no foreign transactions, and a declared vehicle policy. This limits the number of interacting regimes while preserving a meaningful missing-context scenario. If the team instead chooses a limited company, explicitly switch to full-accounting policy and account mapping; do not mix a JDG persona with unexplained company account numbers.

For the hackathon, demonstrate one evidence-complete purchase case: import, identify a missing vehicle fact, ask the founder, apply a verified rule, store the decision and reuse it only when its conditions still match. Keep live filing/payment and annual-close claims outside demonstrated capability. No mandatory accountant click is needed for this bounded demo; unsupported cases remain blocked with a reason. Production rule validation by a qualified domain specialist is a separate requirement from approving every ordinary transaction.

Measure correctness and coverage independently: decision accuracy on adjudicated supported cases; unsafe completion of cases that should block; required-question recall; citation/version accuracy; duplicate/correction handling; and completion rate across all incoming cases. Report sample size and unsupported categories. A system that blocks everything is not an effective end-to-end service, and four successful examples cannot establish 100% correctness across Polish accounting.

## 6. Remaining research and implementation gaps

- Select the first legal form, income-tax regime and record-keeping framework with the team.
- Validate the precise fuel/vehicle rule against the applicable current text and facts; this report does not certify a universal 50%/100% decision.
- Determine the production provider's legal service model, insurance, representation/signature arrangements and responsibility allocation.
- Build a full obligation matrix before claiming PIT/CIT, payroll, ZUS, annual statements, foreign transactions or all correction scenarios.
- Automate monitoring only after connector behavior, publication latency and source completeness have been tested. Public-site availability is not a freshness guarantee. EUR-Lex and EU Court landing-page reads required JavaScript or returned no readable text in this research; no claim is made that their ingestion was tested.
