# G0 pre-credential closure notes

This is a repository evidence record, not a production verification. No credential values are recorded here. Provider quota and license terms require external verification.

## Environment inventory

| Variable | Repository reference / purpose | G0 or later | Provider/service | Secret? | Wiring status |
|---|---|---|---|---|---|
| `GOOGLE_APPLICATION_CREDENTIALS` | `backend/app/core/config.py`, `backend/app/core/firebase.py`; ADC service-account file path | G0 | Firebase Admin / Firestore | Yes (path points to secret material) | Used if set; ADC is otherwise used. Example path is ignored by `**/secrets/`. |
| `FIREBASE_PROJECT_ID` | Firebase Admin initialization | G0 | Firebase | No | Wired. |
| `API_V1_PREFIX` | FastAPI app/router prefix | G0 | FastAPI | No | Wired. |
| `CORS_ALLOWED_ORIGINS` | FastAPI CORS middleware | G0 | FastAPI | No | Wired; production origins must be set during deployment. |
| `JSEARCH_API_KEY`, `RAPIDAPI_HOST` | JSearch collector client; request authentication/host | G0 for configured collection | JSearch/RapidAPI | Yes / no | Wired in collector. No frontend or read-route provider calls. |
| `JSEARCH_TIMEOUT_SECONDS`, `JSEARCH_MAX_RETRIES`, `JSEARCH_RETRY_BACKOFF_SECONDS` | JSearch client transport controls | G0 | JSearch/RapidAPI | No | Wired. No quota claim is made. |
| `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `ADZUNA_COUNTRY`, `ADZUNA_TIMEOUT_SECONDS`, `ADZUNA_MAX_RETRIES` | Adzuna client credentials, country and transport controls | G0 for configured collection | Adzuna | Yes for credentials | Wired in collector. No frontend or read-route provider calls. |
| `GITHUB_TOKEN`, `GITHUB_TOPIC`, `GITHUB_TIMEOUT_SECONDS`, `GITHUB_MAX_RETRIES` | GitHub adoption snapshot collector | G0 for configured collection | GitHub API | Token is secret | Wired in collector; token optional. |
| `SKILL_INTELLIGENCE_DB_PATH`, `SKILL_INTELLIGENCE_MIN_PERIODS`, `SKILL_INTELLIGENCE_READ_BACKEND` | SQLite parity/validation path and minimum periods; API defaults to Firestore | G0 | Internal | No | Firestore is production API source. SQLite remains test/parity only; see below. |
| `GEMINI_API_KEY`, `GEMINI_MAX_CALLS_PER_MINUTE`, `GEMINI_MAX_CALLS_PER_DAY`, `GEMINI_MAX_CALLS_PER_USER_PER_HOUR`, `GEMINI_MAX_INPUT_CHARS`, `GEMINI_MAX_OUTPUT_TOKENS`, `GEMINI_REQUEST_TIMEOUT_SECONDS` | Grounded explanation service and application-side usage guardrails | Later | Gemini / Firestore | API key is secret | Wired. Atomic call reservations use Firestore; configured limits are application guardrails, not provider free-tier claims. Prompt size is character-bounded and output tokens/timeouts are capped. Configure Firestore TTL for `expires_at` in `gemini_usage_budgets` to remove expired budget and deduplication records. |
| `TALENTSCOPE_API_BASE_URL` | Frontend authenticated API clients; when unset, local `localhost:3000` / `127.0.0.1:3000` frontends use the matching host on port `8000`; other deployments default to the current page origin | G0 | FastAPI | No | Wired; configure the runtime value when the API is served from a different origin. |
| `TALENTSCOPE_FIREBASE_CONFIG` | Optional `window`-provided Firebase web config in `src/auth/firebase-client.js` | G0 | Firebase Auth web SDK | Web config is public client configuration, not a server credential | Optional override. A Firebase web API key is present in source; it is not an Admin credential and should have appropriate Firebase/API-key restrictions. |

`.env.example` contains only placeholders/defaults. Root `.gitignore` ignores `.env` and `.env.*` and then explicitly allows `.env.example`; `**/secrets/` ignores service-account files. No `.env` was created or inspected for values in this pass. The obsolete `MARKET_COLLECTION_ADMIN_UIDS` example was removed because the user-triggered collection route no longer exists.

## Provider matrix

| Provider | Signal family / purpose | Credentials | Collection path | Firestore destination | `history_type` | Backfill / accumulation | Fallback, failure and optionality |
|---|---|---|---|---|---|---|---|
| JSearch | Employment/job-posting demand; collected postings become skill demand observations | `JSEARCH_API_KEY`, `RAPIDAPI_HOST` | Existing `JSearchProvider` invoked by `collect_market_data` | `skill_market_signals`; job documents in `jobs` | `platform_collected` | No historical backfill. Repeated scheduled runs accumulate periods. | Optional when unconfigured. Per-provider failure is recorded in `fetch_runs`; no synthetic fallback. Quota/license: requires external verification. |
| Adzuna | Employment/job-posting demand; separate provider provenance | `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `ADZUNA_COUNTRY` | Existing `AdzunaProvider` invoked by `collect_market_data` | `skill_market_signals`; job documents in `jobs` | `platform_collected` | No historical backfill. Repeated scheduled runs accumulate periods. | Optional when unconfigured. Per-provider failure is isolated and recorded. Quota/license: requires external verification. |
| GitHub | Public software adoption signal, not employment demand | `GITHUB_TOKEN`, `GITHUB_TOPIC` | Existing GitHub snapshot provider in `collect_market_data` | `skill_market_signals` | `snapshot` | No historical backfill; snapshots are not converted into history. | Optional. Failure is isolated and recorded in `fetch_runs`; no zero/synthetic substitute. Quota/license: requires external verification. |
| Stack Exchange | Public developer interest signal, not employment demand | No configured credential variable | `StackExchangeHistoricalProvider` used by the explicit historical backfill service | `skill_market_signals` | `backfill` | Historical backfill exists. Platform collection does not turn it into job demand. | Optional source; provider failures/coverage errors are reported by backfill result. Quota/license: requires external verification. |
| Gemini | Grounded explanation only; no market-number source | `GEMINI_API_KEY` | Centralized `LLMExplanationService`, only after validated facts are prepared | `gemini_usage_budgets` stores atomic minute/day/per-user counters and request deduplication keys | N/A | No backfill or collection | Optional. Deterministic grounded answer is used when unavailable, over budget, timed out, rate-limited, or invalid. Application limits default to 60 calls/minute, 1,500/day, and 30/user/hour; prompt size defaults to 12,000 characters, output to 1,024 tokens, and timeout to 5 seconds. Output and timeout are hard-capped; values are configurable guardrails, not provider quota terms. Firestore TTL should be enabled for `expires_at`. |

Provider field mapping verified in code:

| Provider field | Normalized field | Storage/API field | Note |
|---|---|---|---|
| JSearch `job_id`/`job_uid` | `Job.job_id` and posting `provider_job_id` | `jobs.job_id` plus `jobs.source_job_id`; API `job_id`; observation `posting_id` | Provider-supplied identifier; missing IDs are not fabricated for stored provider jobs. |
| JSearch `job_title`, `employer_name` | `title`, `company_name` | same `jobs` fields and API fields | Nullable when absent. |
| JSearch `job_city`, `job_state`, `job_country` | `city`, `region`, `country`; display `location` | same fields in `jobs` and API | Uses provider values; no inferred region/category. |
| JSearch `job_category` | `category` | `jobs.category`, API `category` | Nullable when absent. |
| JSearch `job_apply_link` / `job_google_link` | `source_url` | `jobs.source_url`, API `source_url` | Uses supplied provider URL. |
| JSearch posted timestamp fields | `posted_at` | `jobs.posted_at`, API `posted_at` | Raw supplied value is retained as text. |
| Adzuna `id`, `title`, `company.display_name` | `provider_job_id`/`Job.job_id`, `title`, `company_name` | `jobs.job_id` plus `jobs.source_job_id`; API `job_id`, `title`, `company_name` | The code falls back to a deterministic content hash for internal posting deduplication; no job document/API job ID is written without the provider ID. |
| Adzuna `location.area`, `location.display_name` | `city`/`region` are not separately normalized; `location` uses area text or query | `jobs.location`, API `location` | City/region are unavailable as distinct fields in this adapter. |
| Adzuna `country` from request, `category.label`, `redirect_url`, `created` | `country`, `category`, `source_url`, `posted_at` | same `jobs` fields and API fields | Country is the collection parameter; category and timestamp are nullable if absent. |

## Data state and provenance

The active Skill Intelligence endpoint keeps its existing `data_status` values for compatibility (`available`, `insufficient_data`, `pending_source_data`, `error`) and adds optional `data_state`: `ready`, `partial`, `building`, `stale`, or `insufficient_data`. Daily platform collection is documented at 03:15 UTC, so the centralized policy in `app/analytics/freshness.py` allows platform-collected demand and adoption snapshots 48 hours (one daily interval plus one full interval of operational grace). It uses collection timestamps (`created_at`) rather than provider publication dates. A validated result whose relevant source observations are all beyond the allowance is `stale`; a mixture of fresh/stale or fresh/unknown observations is `partial`; missing collection timestamps without fresh evidence remain `building`. Backfill and other non-periodically refreshed history are excluded and cannot become stale simply by age. Empty applicable evidence remains `insufficient_data`. No missing observation is converted to zero. Market jobs currently expose `available`, `empty`, or `unavailable`; there are no separate active Market/Job intelligence trend APIs to normalize in this pass.

Skill response preserves the backward-compatible `calculation` object and now adds optional `provenance` and fetch-run linkage where known. New scheduled demand observations store their actual `fetch_run_id`; existing observations without it remain explicitly unlinked. Per-source metadata reports observed counts and periods from the API's filtered observation set and the actual latest run ID/time where present. No source URL or `data_origin` is invented: those are still unavailable in the skill observation contract. Historical records lacking a trustworthy collection timestamp are not presented as fresh.

## Demo boundary

The home market panels and personal intelligence overview in `src/app/app.js`, workforce/market prototypes in `src/data/market-data.js` and `src/data/company/company-data.js`, and Employee/Company portal pages use local illustrative data and carry prototype/demo copy. The home shell now states which panels are illustrative; missing overview values in the Market/Skill/Job exploratory panel render as an em dash, not zero. `src/pages/individual/market/MarketIntelligence.js`, the job-trend panel and AI Assistant now identify their content as illustrative. The separate dedicated Skill Intelligence screen uses the backend response and empty/error states. Hardcoded sample data remains in the source because its UI is still a prototype; it is not a validated Market/Job evidence source.

SQLite remains only in the parity/validation implementation selected by internal tests or an explicit validation-only call. Normal `GET /api/v1/skills/intelligence` delegates to `get_skill_intelligence_from_firestore`; its correctness path does not depend on SQLite. Production Firestore history migration, collector deployment/scheduling, credentials, authenticated browser paths and end-to-end source trace remain external verification requirements.

## Relationship integration

The authenticated Employee UI can search active Firestore company profiles, submit a connection request, and read persisted connection state. Company Admin can create an invitation through the existing authenticated `POST /api/v1/company-relationships/invitations` route; the backend checks verified company ownership, connected membership, and duplicate active invitations before persisting the token hash. The UI displays the returned one-time link only after success and explicitly says that no email is sent. `GET /api/v1/company-relationships/invitations` lists persisted invitations for the verified company owner and returns safe metadata only; it omits raw tokens and token hashes. Pending employee connection requests use the existing list/review routes. These flows cannot be runtime-verified without Firebase credentials.

## Collection scheduling evidence

There is no scheduler resource active in this repository. `backend/deploy/deploy-collector.ps1` defines the intended operational mechanism: Cloud Run Job `talentscope-market-collector`, invoking `python -m app.scripts.collect_market_data --country <country>`, and Cloud Scheduler job `talentscope-market-collector-daily` at `15 3 * * * UTC`. Its default mode is validation-only; `-Apply` requires external project, image, IAM service accounts, APIs and Secret Manager values. This pass did not apply it or claim a successful run.
