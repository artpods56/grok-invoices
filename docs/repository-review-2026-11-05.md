# Repository improvement review

Scope: current frontend loading paths, read proxy, invoice drawer, deployment checks and branding. This is a targeted engineering review, not a complete security or accounting audit.

## Assessment

The shared FastAPI service/domain/unit-of-work architecture and read-only dashboard provide a sound separation of responsibilities. Public read projections, role-specific MCP entrypoints and existing tests are useful foundations. The main issues found in this pass concern frontend failure isolation and request fan-out rather than a need to replace the architecture.

## Improvements implemented

- Invoice detail loading previously launched one request per invoice at once. It now uses at most six workers, preserves order, stops queued requests on failure/cancellation, and checks returned invoice/posting relationships.
- A failure loading postings previously prevented a fresh invoice snapshot from appearing. Invoice records now remain available while Decisions, Sources and Precedents show an explicit unavailable state. Missing detail data is not described as an empty decision history.
- Invalid backend URLs previously escaped the proxy error handler. Invalid configuration now fails with a controlled 502 without leaking credentials.
- Opening the invoice drawer now locks background scrolling and restores it when closed.
- The sidebar uses the API company name, masked in privacy mode, with ellipsis for long names.
- CI builds the frontend before contacting the deployment server, in addition to running its tests.
- Added a generated pastel brand mark to the sidebar, browser metadata and README. Next.js optimizes the sidebar image. See [logo provenance and exact prompt](design/logo-v2.md).

## Verification

- Frontend: 45 tests passed; Next.js production build passed.
- Backend: 60 tests passed, one live test deselected. No live KSeF or bot workflow was run.
- Browser: new logo loaded; injected a local detail-only HTTP 503 and confirmed the invoice row remained visible while Decisions showed the error. Restored normal fetch after the test.
- Browser: drawer scroll locking/restoration verified; 390 × 844 viewport had no page-level horizontal overflow.
- Existing untracked Hyperframes work was left untouched.

## Remaining limits

Every refresh still reads detail records for all invoices; bounded concurrency controls load but does not replace server-side pagination or a future aggregate read endpoint. The new logo is a raster asset, not a vector master. Passing checks here does not establish production deployment acceptance.
