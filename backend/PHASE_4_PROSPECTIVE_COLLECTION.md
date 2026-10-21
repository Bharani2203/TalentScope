# Phase 4 prospective collection: fixture workflow and measurement contract

## Current state

This repository now has a fixture-only scheduled workflow and a fixture CLI path. The workflow runs at **03:15 UTC daily** and supports `workflow_dispatch`. Both paths run the same `collect_market_data` service through `OfflineFixtureProvider`; neither enables JSearch, Adzuna, Firebase, Firestore, nor external HTTP. Each invocation uses a new SQLite file under the runner's temporary directory. The file is ephemeral and is not committed or uploaded as an artifact.

This is scheduler configuration and offline fixture evidence only. Workflow event, GitHub run ID, and attempt are passed into the local run record as provenance. The runner database remains temporary, so this does not provide durable history across executions. The workflow has not been installed/enabled or observed running in GitHub Actions. It is not a live scheduled collection.

## Versioned panel and stored measurement

The fixture panel uses provider `adzuna` as the adapter identity, country `in`, location `Chennai`, query `software developer`, one page of at most 10 results, panel `fixture-panel-v1`, extractor `skill-extractor-v1`, and a daily fixture schedule. The real collection panel remains `job-demand-v1`; a production operator must approve and freeze a specific source/geography/query/page-size panel and schedule before live collection. Query identity includes panel, geography, query, provider, pagination, provider-default sorting, date basis, deduplication policy, skill registry version, extractor version, metric definition, and UTC-month granularity. A change to any of these dimensions starts a distinct identity.

The observation contract stores one `job_postings` demand observation per deduplicated posting and canonical skill, with collection timestamp and UTC month as the observation period. Provider posting time is separate. The run ledger separately records fetched, normalized, validated, recognized-skill, unmatched, duplicate, rejected, filtered and per-skill matched-posting counts, pagination, provider totals when returned, collection timestamps/window, panel/query/extractor versions, provenance, completeness, and terminal status. Sampled posting share remains disabled: adding query identity dimensions does not create a share measurement. No share or national-demand interpretation is derived from these counts.

The current Adzuna response field called `count` is retained only as provider diagnostics/coverage context. Its semantics as unique postings or a comparable denominator are not established here. Sampled posting share is therefore **not enabled**. If introduced later, its numerator, eligible/deduplicated denominator, unmatched classification count, and coverage status must be separately validated; unmatched records must remain visible. No provider total becomes a skill share.

## Provider capability evidence and limits

- JSearch's official RapidAPI endpoint documentation describes `cursor`/`num_pages` pagination, a maximum of 20 pages, and `date_posted` windows (`today`, `3days`, `week`, `month`). This supports current filtered search, not retrieval of historical snapshots by month. The existing adapter requests a current/recent search; it cannot reconstruct prior hiring observations. Plan quotas/cost vary; the marketplace lists plan limits, so the account plan must be verified by the owner. [JSearch endpoint docs](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch/playground/Job%20Search) · [JSearch plans](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch/pricing)
- Adzuna's official Search docs describe country/page path parameters, page results, `results_per_page`, `what`, `where`, and a `created` field on advertisements. The official API also documents a historical **salary** endpoint; that does not establish historical job-ad snapshots. The search response's `count` is not treated as unique postings or a denominator. Account-specific quotas, storage/reuse rights, retention terms, and whether the current India plan permits this use remain owner-verification items. [Adzuna Search docs](https://developer.adzuna.com/docs/search) · [Adzuna API overview](https://developer.adzuna.com/overview) · [Adzuna endpoint reference](https://developer.adzuna.com/activedocs)
- No live API request was made. Public documentation does not establish the project's account plan, applicable contract terms, historical snapshot availability, or permission to retain/reuse raw job descriptions. Do not retain live raw payloads until terms are reviewed; obtain provider and account-owner approval before live use.

Historical hiring data starts with the first authorized prospective collection. No prior months are fabricated, interpolated, backfilled from current listings, or sourced from adoption/community/reference datasets.

## Persistence and safety boundaries

The fixture CLI requires an explicitly supplied, new `.sqlite3` path beneath the OS temporary directory. It constructs settings without reading process environment or dotenv configuration, uses the existing `MarketDataStore` schema plus additive `market_fetch_runs` and `market_fixture_postings` tables in the same SQLite file, and marks fixture observations/postings/runs `data_origin=test`. Normal market-observation reads exclude this test origin. Fixture postings contain only deterministic synthetic test data; raw payloads are not archived. No real provider/fetch-run Firestore store is selected.

Normal collection still uses the existing configured production-capable storage path and is intentionally not invoked by this workflow. Before a live scheduler is proposed, the owner must approve provider and account plan, query panel/geography/frequency, retention terms, persistence environment, and execution identity. It must then be configured to use an explicitly approved non-production target with no fallback to production. This workflow does not yet provide that live mode. Repository privacy, data-branch policy/token permissions, and account-specific provider retention/reuse terms cannot be verified from this local checkout. Therefore no JSONL data-branch ledger is selected or wired as a live system of record. An explicitly approved non-production Firestore target is an alternative only after its project, credential boundary, and rules are approved; it must not be a fallback. The present fixture SQLite database is a temporary test/rebuild target only.

## Readiness and scheduler evidence

Trend and Skill Health remain gated by at least four consecutive comparable completed monthly periods with a valid denominator where required. Forecasting remains gated by at least 24 such periods plus chronological holdout evaluation against seasonal-naive; half-life remains gated by 36 consecutive normalized periods and statistically supported decline. The repository-default SQLite path (resolved with model defaults without consulting process environment) was checked read-only: `market_observations` exists and contains **0 rows**, with no earliest/latest period. The environment-selected database target was not verified.

Evidence status:

1. Scheduler code/configuration exists: fixture workflow file exists; application scheduler remains disabled by default.
2. Offline fixture workflow path: exercised locally through its CLI and unit tests; GitHub Actions itself has not run.
3. Workflow installed/enabled: unverified.
4. Manual fixture run in GitHub: unverified.
5. Scheduled run observed: no.
6. Approved live provider collection: no.
7. Persisted run/observations: verified only in isolated test/temp SQLite databases; no genuine observation exists in the local configured DB.
8. Historical readiness gates: none satisfied.
