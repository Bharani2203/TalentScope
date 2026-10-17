# Phase 2 historical backfill

The controlled backfill command currently supports Stack Overflow question-tag
history through the Stack Exchange API. It counts uniquely returned questions
whose source `creation_date` falls inside each inclusive UTC month and whose
tags contain the registry-mapped tag. The resulting observations are
`signal_type=interest`, use `skill_market_signals`, and retain one stable series
per exact tag. They are not job-demand observations.

Run `python -m app.scripts.backfill_market_data --help` from `backend`. A dry run
is the default; pass `--execute` only to persist the observations. The range is
inclusive and must end before the current UTC month. Failed or incomplete months
are listed as coverage gaps and do not become zero observations. A completely
enumerated empty month is stored as zero because the source returned no matching
records for that exact tag and date range.

The API allows 100 records per page and anonymous paging only through page 25.
When a range still has more pages, the backfill recursively divides that date
range and enumerates each half. Rate limits, API backoff, malformed data, and
network failures produce a partial or failed fetch run; no account rotation or
quota bypass is used. The operation is explicit CLI work and is not called by
the frontend or a scheduler.

Wikipedia also has a separate, local-only provider backfill. Its default is a
dry run; `--execute` makes live Wikimedia requests and writes to the configured
SQLite `market_observations` table. This path does not write Firestore and must
not be treated as production Firestore evidence. The current local table has no
observations, and no pageview backfill was run in this phase:

```powershell
python -m app.scripts.backfill_wikipedia --skill python --start 2025-01 --end 2025-12
python -m app.scripts.backfill_wikipedia --skill python --start 2025-01 --end 2025-12 --execute
```

The standard shared intelligence reader uses Firestore, so rows written only by
this SQLite backfill are not visible to that reader. If pageview history is
approved for production use, a bounded migration can export selected validated
rows to the existing Wikipedia JSON-loader format, run its dry-run validation,
then write explicit batches of at most 450 observations with the existing
Firestore loader. Preserve the article, monthly period, unit, series ID, source
URL, and import-run provenance. No SQLite-to-Firestore migration has been run.

The existing SQLite observation table is migrated additively and idempotently
to retain canonical skill IDs, denominators, run/series/query provenance,
quality, confidence, observation counts, extractor versions, annotations, and
creation timestamps. Source metric, unit, and evidence references remain in
`metadata_json`.

JSearch and Adzuna expose recent/current job listings; they are not used to
create historical observations. GitHub Innovation Graph language and topic
datasets are different: the local CSVs contain quarterly unique-developer
counts from 2020-Q1 through 2026-Q1. `ingest_reference_data` stores them in
local SQLite and Skill Intelligence reads the mapped India series there.
These are developer-activity/adoption signals, not job demand. Their quarters
are never converted to months, and their raw counts do not qualify for
normalized-share Skill Health, Half-Life, or the monthly forecast model.
The catalog exposes trend-ready skill IDs and unique-skill readiness counts
from the shared trend engine. Current local counts are 8,784 canonical IDs,
42 skills with mapped GitHub history, 40 trend-ready skills, 40 with a
four-period Theil-Sen rate, and 41 with an adjacent-quarter change. The trend
count exceeds the earlier 39 because Google Cloud has a valid latest run of
five contiguous topic quarters. These are local developer-activity analyses,
not production market-demand trends.

The local O*NET files and the GitHub CSVs can be re-ingested idempotently into
SQLite from `backend`:

```powershell
python -m app.scripts.ingest_reference_data
```

An ESCO v1.2.1 archive is present locally and can be inspected without
extraction or import:

```powershell
python -m app.scripts.ingest_reference_data --inspect-esco-only
```

That command does not ingest ESCO skills; they are not currently included in
the SQLite catalog. O*NET and ESCO taxonomy rows are reference data, not dated
market observations.

The offline Stack Exchange and Wikipedia JSON loaders validate locally by
default. Review the summary first. Only add `--execute` after authorizing the
write, and keep each input at or below 450 observations (the default
per-execution cap); no live provider call or bulk backfill is started by these
commands:

```powershell
python -m app.scripts.load_stackexchange_shares --input .\data\stackexchange-months.json
python -m app.scripts.load_stackexchange_shares --input .\data\stackexchange-months.json --execute --max-observations 450
python -m app.scripts.load_wikipedia_pageviews --input .\data\wikipedia-months.json
python -m app.scripts.load_wikipedia_pageviews --input .\data\wikipedia-months.json --execute --max-observations 450
```

Both loaders preserve the provider-specific tag/article, monthly range, units,
denominator when supplied, input-file hash, and import run ID. Explicit
execution writes idempotently to the existing Firestore
`skill_market_signals` collection. These commands have not been run as part of
this phase.

The trend calculator keeps sources, signal families, and series definitions
separate. Stack Overflow interest does not alter job-demand trends. Local
GitHub quarterly developer counts use the shared Theil-Sen trend engine and
retain quarter periods; trend direction requires at least four contiguous,
completed quarters. Velocity is the Theil-Sen slope in unique developers per
quarter. Period-over-period change is emitted only when the immediately prior
completed quarter exists. Missing periods and denominators are not synthesized,
and developer activity is not job-demand evidence.
