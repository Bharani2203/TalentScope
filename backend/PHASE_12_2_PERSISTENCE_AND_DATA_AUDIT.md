# Phase 12.2 — Persistence observability and historical data audit

## Run verification boundary

The reported collection ID `dfeeb72180154b8399d8ff73de4ae3d9` was not found in the local SQLite database. Read-only inspection found 0 rows in `market_collection_runs` and 0 rows in `market_observations`; the database has no `jobs` table. No Firestore request was made, so presence and contents of the reported Firestore records remain unverified. The ID in the CLI response is the aggregate `collection_run_id`; individual provider documents in `fetch_runs` use different document IDs and link back through `collection_run_id`.

## Persistence routing

| Record | Normal write path | Identity/link | Offline verification limit |
|---|---|---|---|
| Aggregate collection result | Returned by the CLI; there is no separate aggregate Firestore collection writer in the collector | `run_id` is copied to each provider record as `collection_run_id` | The reported output is not evidence that provider records were persisted |
| Provider fetch-run metadata | Firestore `fetch_runs` via `FirestoreFetchRunStore` | Firestore document ID is the provider `fetch_run_id`; record carries `collection_run_id`, source, query/panel, geography, times, counts, coverage and errors | Cannot inspect the reported run without contacting Firestore |
| Normalized job postings | Firestore `jobs` via `store_collected_market_jobs` / `store_jsearch_jobs` | Document key is source plus provider ID (hashed only when Firestore document-key restrictions require it); payload retains `source_job_id`, `source`, `fetch_run_id`, `fetched_at` and normalized fields | No local jobs table; current Firestore rows unverified |
| Market observations | Firestore `skill_market_signals` by default; `MarketDataStore` SQLite when `skill_intelligence_read_backend=sqlite`; injected stores in tests | Stable deterministic observation ID; observation links to provider run ID, query ID and panel version | The setting used by the past command is not recorded in its old run metadata. Default code setting is Firestore; `.env` was not inspected. Current process environment does not override the setting, but that does not prove what the prior process used. |
| Job-search capability | `GET /api/v1/market/jobs` calls `search_stored_jsearch_jobs`, reading Firestore `jobs` only; it does not call a provider | Results preserve job/provider ID, source, fetch-run ID, fetched time and URL where stored | The injected test validates the read path; it cannot confirm that this specific run's ten jobs are present |

`observations_inserted` is the count of newly inserted observation documents, not a count of all observations already present. Job persistence returns the count of source/provider IDs whose Firestore batch upsert completed. Before this phase, the collector ignored that return value and exposed validated postings without a persisted-posting count. It also accepted `partial_failure` as a successful CLI exit. A failed batch could therefore leave the persistence result unclear to the caller.

Phase 12.2 adds backward-compatible fields to the CLI result and each provider fetch-run record:

- Per-provider fetched, validated, rejected, filtered and unmatched record counts.
- Confirmed posting upsert count, unconfirmed posting count and a persistence status (`confirmed`, `not_attempted` or `unknown`).
- Observation insertion count/status and selected observation backend (`firestore`, `sqlite`, `injected` or `dry_run`).
- Structured reasons such as `pagination_incomplete`, `postings_without_skill_observations`, `job_persistence_unconfirmed` and `observation_persistence_unconfirmed`.
- Collection-level observation insertion result linked into each provider run by `collection_run_id`.

`null` with status `unknown` means the write outcome could not be confirmed; it is not reported as zero persisted. A confirmed observation count means new IDs inserted by this invocation; stable-ID duplicates may already exist. The CLI exits nonzero for a returned `partial_failure` or `error` result after printing its details. Configuration exceptions also exit nonzero, though they can occur before a collection response exists to print. Existing response fields remain for compatibility.

## Local dataset inventory (read-only)

Counts below are from `backend/data/skill_intelligence.sqlite3`, opened with SQLite `mode=ro`. No database contents were modified.

| Data family | Confirmed locally | Meaning and remaining unknowns |
|---|---|---|
| ESCO taxonomy/reference | 3,039 occupations; 13,939 skills; 126,051 occupation-skill relations | Static reference taxonomy, not historical market demand. Dataset version and source metadata are in the existing reference ingestion path. |
| O*NET taxonomy/reference | 1,016 occupations; 18,200 essential-skill rows; 18,460 related-occupation rows; 31,821 software-skill rows | Static occupational reference data, not market observations. |
| GitHub Innovation Graph | 180,338 language rows and 82,591 topic rows, each spanning 2020-Q1 to 2026-Q1 | Historical quarterly developer adoption/activity. It is not hiring demand, and its quarterly periods are not converted into months. |
| Historical market observations | 0 rows in local `market_observations` | Stack Exchange and Wikipedia historical backfill are supported by code; no historical market-observation rows are present in this local DB. Firestore history remains unknown. |
| Platform-collected market observations | 0 rows locally; 0 local collection-run rows | Code supports JSearch/Adzuna demand and GitHub snapshots. The reported Adzuna result is not locally confirmed; Firestore is uninspected. |
| Current provider snapshots | No separate local snapshot/job table; no rows in local `market_observations` | Adapters support current JSearch/Adzuna listings and GitHub repository-topic snapshots. Whether the reported Adzuna listing snapshot persists in Firestore is unknown. |
| Stored job postings | No local `jobs` table | The Firestore storage/search path is supported by code and dependency-injected tests. Records from the reported run remain unverified. |
| Forecast outputs | No forecast-output table; local `market_calculation_cache` has 0 rows | Forecast functions exist in code; no local stored forecast output was found. Firestore or other runtime caches were not inspected. |

The reported 10 validated postings and 5 created observations remain command-output figures, not independently verified persisted counts. The five observation rows and ten provider IDs were not read. By contract, each generated posting-skill observation has `signal_type=demand`, `unit=job_postings`, value 1, collection time in `observed_at`, provider posting time separately in `provider_posted_at` when parseable, and no denominator assigned at collection. Exact skill names, row uniqueness, provider identifiers and per-record provenance for this run cannot be asserted without reading its Firestore records.

## Partial status and pending sources

For the reported counts, ten normalized postings and five created observations imply that at least some postings produced no skill observation; collection code records those as `records_unmatched` and marks the run partial with `postings_without_skill_observations`. The Adzuna adapter also marks pagination incomplete when its provider total is missing or exceeds the returned page. The supplied output does not include `provider_total_count` or `pagination_complete`, so whether pagination was an additional reason cannot be resolved. `partial_failure` is an incomplete-coverage result, not necessarily a failed HTTP request. The new result fields expose the precise reason on future runs.

Pending sources are calculated from known providers not configured/selected for that invocation. They are not failed runs. Actual attempted provider failures are kept separately in `sources_failed` and the per-provider status/error fields.

## Readiness and evidence boundary

The single collection period reported is `2026-10`, the then-current, incomplete month, and the run is partial. It does not create historical months or unlock analytical capability. Existing gates remain unchanged:

- Trend: at least 4 consecutive comparable completed monthly periods.
- Skill Health: at least 4 comparable completed monthly periods and a valid positive source-specific denominator; raw posting counts alone are ineligible for its normalized-share score.
- Demand forecast: at least 24 consecutive comparable completed monthly periods plus chronological holdout evaluation against the seasonal-naive baseline.
- Skill Half-Life: at least 36 consecutive normalized monthly observations and statistically supported decline.

ESCO/O*NET reference data and GitHub quarterly adoption history cannot fill these hiring-demand periods. No synthetic observations, inferred zeroes or forecasts are introduced.

## Python warning assessment

Repository metadata declares Python 3.10+ in `README.md`; there is no Python version pin, `pyproject.toml`, or backend Dockerfile in the repository. The inspected interpreter is Python 3.10.11. `backend/requirements.txt` constrains `firebase-admin>=6.5,<8.0`, but does not directly pin `google-cloud-firestore` or `google-api-core`.

Installed local package metadata (read only) reports `firebase-admin 7.7.0` (`Requires-Python >=3.9`), `google-cloud-firestore 2.34.1` (`>=3.10`) and `google-api-core 2.30.3` (`>=3.9`). Firebase Admin declares transitive lower/upper bounds for Google API Core and Firestore. These metadata ranges allow Python 3.11, but the runtime emits a Google-library warning that Python 3.10 will no longer receive further updates. Only Python 3.10 is installed in the current Windows launcher; a Python 3.11 run was not performed. Thus 3.11 is a plausible, metadata-compatible upgrade path, not yet a tested project runtime.

Before a separately approved Python upgrade, provision a clean Python 3.11 environment, install the unchanged requirements there, run the complete backend suite (`python -m pytest -q` from `backend`), run Firebase/emulator isolation and storage/provider test groups, verify app imports/startup under the configured emulator-only test environment, and run `git diff --check`. Do not copy production credentials into that environment. This phase does not upgrade or reinstall anything.

## Offline tests and owner follow-up

Dependency-injected tests cover successful job upsert counts, unknown persistence after write exceptions, observation backend reporting, per-provider run metadata, partial-reason reporting, and job-search retrieval preserving source/job/fetch metadata. They do not call a live provider or Firebase/Firestore.

An authorized project owner must use an approved read-only Firestore inspection to verify that `fetch_runs` contains the provider document whose `collection_run_id` equals the reported aggregate ID; then verify its final pagination/count/reason fields, the associated `jobs` rows and their `source_job_id`/`fetch_run_id`, and `skill_market_signals` rows filtered by the provider fetch-run ID. Confirm the observation backend from the run record and inspect its actual value, unit, denominator, quality, timestamps, canonical skill IDs and deduplication. Do not rerun collection to fill missing evidence. A bounded stored-job search may then verify retrieval. This manual check is required before treating any of the reported records as verified real evidence.
