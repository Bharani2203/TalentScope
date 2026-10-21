# Phase 12 — First real market collection preparation

This document prepares an operator-reviewed, one-time sampled collection. No provider request or Firebase/Firestore access was performed while preparing it. Provider code being present does not establish that it is enabled, configured, permitted, or operational.

## Source suitability

| Source / adapter | Signal and category | Schema / time resolution | Required configuration (names only) | Backfill / snapshot support | Provenance / deduplication | Limitations / gaps |
|---|---|---|---|---|---|---|
| JSearch / `JSearchProvider` | Job listings; hiring-demand sample | Normalized posting fields (`job_id`, title, description, location, skills, employer, URL, posting date); one page, recent-month filter | `JSEARCH_API_KEY`; `RAPIDAPI_HOST` has a code default | Current listing fetch only; no historical backfill; one-page snapshot | Provider job ID retained; adapter removes repeated IDs; collection run/query/panel and posting date are separate; stable observation identity is idempotent | No explicit result-count cap in its existing search service; provider pagination/coverage is limited; historical vacancy counts cannot be reconstructed |
| Adzuna / `AdzunaProvider` | Job listings; hiring-demand sample | Normalized posting fields; page 1, up to 50 records, current results; query, country, optional location | `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`; `ADZUNA_COUNTRY` default is in code | Current listing fetch only; no historical backfill; one-page snapshot | Adzuna `id` retained; duplicate IDs filtered; collection run/query/panel, `created` posting date, and `fetched_at` collection date retained; stable observation identity is idempotent | One page may be incomplete; provider total indicates partial coverage; listings can change/disappear; source terms/retention rights and account quota/cost need owner verification |
| GitHub / `GitHubProvider` | Developer adoption/activity, not hiring demand | Repository-topic count snapshot; current point-in-time bounded search (up to 1,000 search results) | `GITHUB_TOKEN`, `GITHUB_TOPIC` | Current snapshot only in this adapter; separate quarterly local Innovation Graph reference data exists | Topic, source, query/panel, collection time, endpoint, and bounded-search quality are retained; observation identity is stable | Topic-search counts are not unique developers or vacancies; API search limit/rate limits mean sampled results; do not merge with demand |
| Stack Exchange / `StackExchangeHistoricalProvider` | Community interest | Unique Stack Overflow questions by mapped tag and source `creation_date`; monthly UTC periods | No required credential in this service; optional quota behavior is reported by the API | Explicit date-bounded historical backfill | Tag, date range, per-month fetch run and source timestamps retained; incomplete months remain gaps, not zero | Community questions are not job demand; anonymous paging capped and recursive date splitting handles coverage; rate limits apply |
| Wikipedia / `WikipediaPageviewsProvider` | Public attention | Monthly English Wikipedia article pageviews | `WIKIMEDIA_USER_AGENT` and timeout/retry settings; no API key | Explicit historical monthly backfill; default local SQLite path | Mapped article, source URL, month, run provenance, and pageview unit retained | Attention is not hiring demand; local backfill writes SQLite, not the Firestore intelligence reader |
| ESCO / O*NET | Reference taxonomy | Static occupations, skills, and mappings; no market time series | Local dataset files and ingestion configuration | Local reference import/inspection, not market backfill | Dataset identity/version and canonical skill mapping where available | Taxonomy is not observed demand, adoption, interest, or attention. ESCO is present locally but not currently loaded into the SQLite catalog per `HISTORICAL_BACKFILL.md` |

The local GitHub quarterly adoption CSVs are a separate reference-data surface. They retain quarterly periods and cannot be re-labeled as monthly job postings.

## Bounded first collection

Recommend **Adzuna**, subject to the project owner verifying account access, permitted use, retention, and quotas. This recommendation is based on the adapter's explicit provider-side page-size control and pagination diagnostics, not on whether a key is configured. The initial request is:

- Provider: Adzuna only.
- Query: `software developer`.
- Country: `in` (India); location: `Chennai`.
- Requested page: 1; page size: 10.
- Expected maximum returned/normalized postings: 10. No second page or scheduled follow-up.
- Source metadata: Adzuna posting ID, title, description, company, location/country, category, redirect URL, provider `created` timestamp, collection timestamp, source, fetch-run ID, query ID, panel version, page size, provider total when present, and coverage status.

The source returns current listings, not a historical time series. If the provider total exceeds 10, the run must be recorded as partial coverage; a small sample must not be presented as the whole Chennai or India market. Malformed records (including missing titles) are rejected and counted. Duplicate source IDs are filtered; conflicting duplicates are not silently merged. Missing or invalid provider posting dates remain null while the collection timestamp is retained separately. A request, authentication, rate-limit, schema, or storage failure must produce a failed/partial run with a safe error category, never success. A successful, explicitly verified empty result is distinguished from an unknown empty/incomplete result.

Adzuna is enabled only if the operator has separately approved it in `MARKET_COLLECTION_ENABLED_PROVIDERS` and its configuration is provided in the approved runtime. The source flag limits this command to Adzuna; it does not read or display credential values. Before running, verify that the target is a non-production, owner-approved Firebase project and that the runtime identity has only the required Firestore permissions. The collector writes provider run records to `fetch_runs`, normalized postings to `jobs`, and canonical observations to `skill_market_signals`. It does not use the local SQLite observation database as the intelligence source of truth.

## Offline verification and analytics compatibility

The provider adapter tests use `httpx.MockTransport`, and collection tests use in-memory stores, write traps, or `tmp_path` databases. They verify normalized source/provider IDs, duplicate filtering, invalid-record rejection, timestamp separation, safe failure states, and test-only dry-run origin. Do not use the live CLI's `--dry-run` as an external-free fixture check: it still calls configured providers to fetch a batch, even though its persistence sinks are disabled.

Posting normalization extracts canonical skills and emits one `demand` observation per distinct posting/skill. Observation `observed_at` is collection time; parseable source posting time is kept in `provider_posted_at`. Stable observation IDs and provider posting IDs make repeated logical records idempotent. Fetch-run records hold the query, geography, source, time window, counts, pagination, and safe errors. A single collection is a current sampled snapshot, not historical evidence.

Keep the existing analytical readiness gates:

- Trend direction: at least four consecutive, comparable, completed monthly periods for the same source/query/panel/geography/skill series.
- Skill Health: at least four comparable monthly periods and a valid positive denominator; demand totals from an incomplete sample do not qualify.
- Demand forecast: at least 24 consecutive comparable completed monthly periods and a chronological holdout evaluation against the seasonal-naive baseline.
- Skill Half-Life: at least 36 consecutive normalized monthly observations with statistically supported decline.

The current readiness audit remains the authority for data quality and eligibility. Do not manually fill gaps, convert GitHub quarters into months, use a single posting batch as history, or weaken a gate to make a capability appear ready.

## Approval checklist and execution command

Before execution, the owner/operator should explicitly approve each item:

- [ ] Adzuna as the sole live provider, with `software developer`, Chennai, India, page 1, maximum 10 results.
- [ ] Provider terms, allowed retention, account quota/rate limit, and any cost (not specified in this repository) verified with the provider/account owner.
- [ ] Approved non-production Firebase project, Firestore rules/permissions, and provider configuration verified without printing secrets.
- [ ] One-time collection only; no scheduler, retry loop, or broadening of query/geography authorized.
- [ ] Returned provider run ID and status reviewed. Confirm `fetch_runs` has source/query/geography, timestamps, counts, page limit, provider total, and coverage/error status.
- [ ] Verify the same run ID and source/provider IDs on `jobs`; inspect a bounded set of `skill_market_signals` for `data_origin=real`, `history_type=platform_collected`, `signal_type=demand`, canonical skill, posting ID, `observed_at`, `provider_posted_at`, query/panel, and quality. Use the authorized project’s read-only console or existing read path; do not query by dumping secrets or user/company records.
- [ ] Stop after this one invocation. Do not schedule additional runs until separately approved.

After explicit approval only, from the `backend` directory in the approved runtime, the bounded command is:

```powershell
.\.venv\Scripts\python.exe -m app.scripts.collect_market_data --provider adzuna --query "software developer" --location Chennai --country in --limit 10
```

This performs a live provider call and writes to the configured Firestore project. Do not run it as part of this preparation phase. The command exits nonzero if the selected source is unavailable or collection fails; a `partial_failure` result is not complete market coverage. Stop/avoid further collection by making no further invocations and leaving the scheduler disabled.
