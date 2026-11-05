# Source access checks

Checked on 2026-11-05 using unauthenticated, read-only HTTP requests. These checks establish accessibility and response shape, not the completeness, correctness, or legal applicability of retrieved content. No recurring job was installed, no xAI request was executed, and no taxpayer data was sent.

## ELI legal metadata

`GET https://api.sejm.gov.pl/eli/acts/DU/2004/535`

- HTTP 200; identifies the VAT Act as `DU/2004/535`.
- Observed `changeDate`: `2026-11-03T00:00:00`.
- The base act's original `entryIntoForce` is `2004-04-20`. This is not an effective date for all later amendments.
- `textHTML` is `true`; available files also include original and consolidated PDF variants.
- Reference categories include amending acts, implementing acts, and consolidated-text announcements. The consolidation references include `DU/2026/1263`.
- [The consolidation announcement](https://eli.gov.pl/eli/DU/2026/1263/ogl) was published on 2026-09-28 and reports a legal-status date of 2026-08-26. Its presence does not prove coverage of amendments after that date.

## ELI change listing

`GET https://api.sejm.gov.pl/eli/changes/acts?since=2026-11-04T00%3A00%3A00&limit=2&offset=0`

- HTTP 200; response is an object with `items`, `count`, `offset`, and `totalCount`, not a bare array.
- Observed `count=2`, `offset=0`, `totalCount=124`. These are transient observations, not stable expectations.
- The first item was `DU/2025/1483` with `changeDate=2026-11-04T09:04:22` and publication in 2025. A record changed recently can concern an older act.
- The second item was `DU/2022/2705`, with `changeDate=2026-11-04T09:14:49` and `entryIntoForce=2023-06-22`.
- [The official OpenAPI contract](https://api.sejm.gov.pl/eli/openapi/) documents `since`, `offset`, and `limit`, with a maximum page size of 500. A real watcher must drain all pages and reconcile changes; the two-item probe did not do this.

`changeDate` is an update signal. It is not evidence that a substantive provision changed on that date or is applicable to today's invoice.

## Empty legal-fragment response

`GET https://api.sejm.gov.pl/eli/acts/DU/2004/535/text.html/art=86a`

- The direct request returned HTTP 200 and a zero-length body.
- This response supplies no evidence for a vehicle VAT rule. It must fail content validation and trigger another verified source/version or a blocked case.
- No conclusion about the current substantive wording of that article was drawn from this request. The research does not treat an arbitrary fragment URL as a successful provision-level integration.

## ZUS RSS

`GET https://www.zus.pl/o-zus/aktualnosci/-/asset_publisher/aktualnosci/rss`

- HTTP 200; parseable XML with an `rss` root and 10 items at inspection time.
- The feed is linked from [ZUS's official RSS directory](https://www.zus.pl/kanal-rss), which also lists technical communications and current explanations.
- News is a discovery signal. A specific calculation still requires its applicable legal basis and period.

## Other inspected sources and limits

- [EUREKA overview](https://podatki.gov.pl/narzedzia/eureka): describes public search for interpretations and binding information. A stable documented bulk/search API was not established by these checks.
- [National Accounting Standards](https://www.gov.pl/web/finanse/krajowe-standardy-rachunkowosci): lists both historical and updated attachments, including a 2026 update. Attachment identity/version matters; first matching title is insufficient.
- [KSeF integrator support](https://ksef.podatki.gov.pl/ksef-na-okres-obligatoryjny/wsparcie-dla-integratorow/): links API environments, contracts, and changelog. No authenticated invoice operation was performed.
- [xAI web search](https://docs.x.ai/developers/tools/web-search): documents live search and domain filtering. This task inspected documentation; it did not verify account/model access, billing, or a running Grok Bot integration.

All production cadences, freshness thresholds, and source-validation gates in the research reports are design recommendations, not guarantees supplied by these services.

## Implemented acquisition probes — 2026-11-05, 19:33 UTC

The new `legal_sources` functions were exercised with read-only requests, without taxpayer
data. Act metadata for `DU/2004/535` returned `changeDate=2026-11-03T00:00:00` and
`validation_status=requires_review`. The change listing returned 2 of 124 items, an explicit
`next_offset=2` and `coverage_complete=false`; this was not a full monitoring scan.

Title search returned a 25-item page with a continuation cursor. Reading the base act's
HTML returned a 20,000-character excerpt with a cursor. This demonstrates acquisition,
not that the base publication is the applicable consolidated wording for a new invoice.

The `art=86a` fragment again returned an empty body. The implemented reader rejected it
with `LegalSourceUnavailable` and reported that no legal evidence was acquired. It did not
approve a deduction from the response. No Grok Bot connection, recurring trigger, policy
activation or source-archive integration was tested by these probes.
