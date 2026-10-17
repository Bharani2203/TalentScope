# TalentScope backend

FastAPI backend for the Individual Portal, including onboarding-profile skills and market Skill Intelligence.

See [G0 pre-credential closure notes](G0_PRE_CREDENTIAL_CLOSURE.md) for the environment inventory, provider matrix, provenance limits, and repository verification boundaries.

## Requirements

- Python 3.10+
- A Firebase project with Authentication and Firestore enabled
- Firebase Admin SDK credentials for local development

## Setup (PowerShell)

From this `backend` directory:

1. Create and activate a virtual environment: `py -m venv .venv` then `.venv\Scripts\Activate.ps1`.
2. Install dependencies: `pip install -r requirements-dev.txt`.
3. Copy `.env.example` to `.env` and set `GOOGLE_APPLICATION_CREDENTIALS` to the path of a Firebase service-account JSON file you obtained securely.
4. Run the API: `uvicorn app.main:app --reload`.
5. Open `http://127.0.0.1:8000/docs` for Swagger UI. Health check: `http://127.0.0.1:8000/api/v1/health`.

Never commit the service-account JSON file or `.env`. For deployed Cloud Run services, use an attached service identity / Application Default Credentials instead of a local key file.

## Firebase configuration note

The Firebase `apiKey` in a web SDK configuration is a client-side project identifier, not a Firebase Admin credential. It is not used by this backend. Firebase Admin authenticates with Application Default Credentials (locally, a service-account file; on Cloud Run, an attached service identity). The Firebase project ID is configured for Admin and Firestore access. Sanitized raw provider responses are archived in Firestore under `raw_response_archives` with chunk documents in each archive's `chunks` subcollection. The payload index exemption is declared in `firestore.indexes.json` and must be applied to the Firebase project before storing production-sized chunks.

The auth dependency in `app/api/dependencies.py` verifies Firebase ID tokens. Firestore access is provided by `app/core/firebase.py`; use it from service modules rather than directly in route handlers.

## JSearch job search

Set a rotated RapidAPI key in the untracked `.env` as `JSEARCH_API_KEY`; `RAPIDAPI_HOST` defaults to `jsearch.p.rapidapi.com`. The existing endpoint `GET /api/v1/market/jobs` reads matching records from Firestore `jobs` only. It accepts `query` and optional two-letter `country`; it never calls a provider. Responses contain normalized job fields and omit unavailable source fields. Collection is performed by the existing operational collector command, not by HTTP read routes.

## Skill Intelligence and market history

`GET /api/v1/skills/my` reads the authenticated user's canonical onboarding skills and proficiency from `users/{uid}`. `GET /api/v1/skills/intelligence?range=6m` reads that profile and Firestore `skill_market_signals`, returning personal and overall-market rankings, actual observation periods, and selected-skill detail. Supported windows are `7d`, `30d`, `3m`, `6m`, and `custom` with `days=7..184`; unsupported filters return HTTP 422 with `error_code=invalid_filter`. Omit `location` to use the saved profile city. Both endpoints require Firebase ID-token authentication. The frontend calls FastAPI only; it does not call external market providers.

The existing collector adapts JSearch, Adzuna, and GitHub providers. Each provider execution is logged independently to Firestore `fetch_runs`; market observations are written to Firestore `skill_market_signals`, which is the intelligence source of truth. The intelligence API reads Firestore and does not depend on SQLite. SQLite remains only in the legacy `MarketDataStore` implementation and validation/parity tests; it is not written by normal collection and is not used by API correctness paths. Do not rely on that local database for production data.

Provider execution is controlled by `MARKET_COLLECTION_ENABLED_PROVIDERS` (a JSON string array such as `["jsearch","github"]`) as well as provider credentials. Names are case-insensitive; currently supported names are `jsearch`, `adzuna`, and `github`. Disabled providers and enabled providers missing their required credentials are not instantiated or called. An unknown provider name fails collection configuration explicitly instead of being silently ignored. Credentials alone do not trigger collection; `market_scheduler_enabled` remains false by default, and providers run only when an operator or an explicitly configured scheduler invokes the collector.

No trend history is included or fabricated. A trend ranking requires at least four consecutive observed monthly periods; until the collector has accumulated enough real data, the API reports an insufficient/pending state and the UI shows its corresponding empty state. Running collection once does not create historical months retroactively.

Run the existing collector command only from an operational scheduler or a controlled operator session:

```powershell
.\.venv\Scripts\python.exe -m app.scripts.collect_market_data --location Chennai --country in
```

This command performs live provider requests and writes to the configured Firestore project; it has no dry-run switch. Do not run it against production for a smoke test. Use an isolated non-production Firebase project and explicitly supplied provider credentials. The authenticated `POST /api/v1/market/admin/collect` endpoint has the same live side effects and requires a verified Firebase custom claim `role=admin`; ordinary authenticated users receive HTTP 403. A safe smoke test should explicitly invoke exactly one of these entry points with a bounded location/country, then verify the returned provider run IDs in `fetch_runs`, canonical observations in `skill_market_signals`, and postings in `jobs`. Repeating the run should not create duplicate logical observations. No live collection or Firestore write is performed by the test suite.

Omit `--location` to collect the configured country/global job-market scope. Production scheduling mechanism: deploy this backend image as a **Cloud Run Job**, then configure **Cloud Scheduler** with a daily UTC schedule to invoke the Cloud Run Jobs `run` API using an attached service account authorized for that specific job. The job command is `python -m app.scripts.collect_market_data`; configure location/country as Cloud Run Job arguments. Collection is not exposed through standard user-facing routes and is never triggered by a page request; the admin collection route is explicitly role-gated. Until that Cloud Run Job and Scheduler are provisioned in the deployment project, collection is operator-run only; this repository does not claim an active production schedule.

Collection requires a persisted fetch-run start record before contacting a provider. If that write fails, the provider is not called. If observations are stored but the fetch-run completion record cannot be written, the collection response reports partial failure; the persisted run may remain marked as running and must be checked during operations.

### Controlled staging smoke prerequisites

Before a staging smoke run, provision a separate non-production Firebase/Firestore project and enable Firebase Authentication, Firestore, Cloud Run, Cloud Scheduler, Secret Manager, and Artifact Registry when used. Apply the repository's `firestore.indexes.json` to that staging project using the deployment team's approved Firebase/IaC process. Configure the backend's Firebase project ID and use Application Default Credentials locally or a dedicated Cloud Run runtime identity with only the required Firestore (`roles/datastore.user`) and named-secret access. The collection route must be called with an ID token whose verified Firebase custom claim is `role=admin`; provision that claim through an authorized Firebase Admin process, not through request JSON. Supply only the required provider secrets through a local ignored `.env` or Secret Manager: `JSEARCH_API_KEY`, both `ADZUNA_APP_ID` and `ADZUNA_APP_KEY`, and/or `GITHUB_TOKEN`. Explicitly set `MARKET_COLLECTION_ENABLED_PROVIDERS` to the intended JSON string array; do not copy production credentials or use a production project.

For one explicitly approved bounded staging run, use the existing command from the `backend` directory:

```powershell
.\.venv\Scripts\python.exe -m app.scripts.collect_market_data --location Chennai --country in
```

Alternatively, call `POST /api/v1/market/admin/collect` with the verified admin bearer token and a bounded `location`/`country` body. Both entry points make real provider requests and write Firestore records; neither is a dry run. Verify every `fetch_runs` provider document has a distinct `run_id` and the returned aggregate `collection_run_id`, then verify the resulting `skill_market_signals` and `jobs` documents. Do not interpret a partial response as a fully recorded run: an unavailable completion write means the provider record may remain `running`, even if observations were persisted. Repeat only in staging to inspect idempotency. No smoke run, live provider call, Firestore access, or deployment is performed by this repository's tests.

### Production collection deployment checklist

The repository includes `deploy/deploy-collector.ps1`. Its default mode validates inputs and prints a deployment plan; `-Apply` performs deployment and therefore requires an authenticated `gcloud` CLI and pre-provisioned cloud resources. Example plan:

```powershell
.\deploy\deploy-collector.ps1 -ProjectId <project-id> -Region us-central1 -Image us-central1-docker.pkg.dev/<project-id>/<repository>/talentscope-backend:<tag>
```

The deployment target is Cloud Run Job `talentscope-market-collector`, invoked by Cloud Scheduler job `talentscope-market-collector-daily` at `03:15 UTC` daily. The job runs `python -m app.scripts.collect_market_data --country in`, with one task, parallelism one, a 900-second task timeout, and one Cloud Run retry. Cloud Scheduler uses OAuth as `talentscope-scheduler-invoker@<project-id>.iam.gserviceaccount.com`, with two trigger retries (up to one hour; 60–600-second backoff) and a 1200-second attempt deadline. Collector logs are written to stdout/stderr and Cloud Run logs; provider outcomes are also recorded individually in Firestore `fetch_runs`. A provider failure is isolated from other provider runs and is not replaced with synthetic observations.

The Cloud Run runtime identity is `talentscope-collector@<project-id>.iam.gserviceaccount.com`; grant it Firestore access (`roles/datastore.user`) and Secret Manager access only to the provider secrets below. Grant the scheduler identity `roles/run.invoker` on this specific job. The deployer needs Cloud Run Job, Cloud Scheduler, Secret Manager, and service-account deployment permissions, including permission to attach the runtime and invoker identities. Enable Cloud Run, Cloud Scheduler, Secret Manager, Firestore, and (when applicable) Artifact Registry APIs. Create these Secret Manager secret names before applying the script: `jsearch-api-key`, `adzuna-app-id`, `adzuna-app-key`, `github-token`. The script references secret version `latest`; no key is embedded in repository files. Public provider collection is conditional on configured secret values. The job writes `fetch_runs`, `skill_market_signals`, and normalized job snapshots in `jobs`. GitHub contributes current adoption snapshots; JSearch/Adzuna contribute collected job-demand observations and job records. Stack Exchange historical backfill is a separate existing operation, not part of this daily job. Cloud resources have not been provisioned by this repository change; verify a successful job execution and scheduler status in the target project before treating scheduled collection as active.

### History type reconciliation

`skill_market_signals.history_type` is limited to `backfill`, `platform_collected`, or `snapshot`. `python -m app.scripts.normalize_history_types` scans and reports counts without writing by default. Only deterministic mappings are eligible: `adoption_snapshot` with adoption signal becomes `snapshot`; legacy `observed_signal` is mapped only when provider and signal identify GitHub adoption, JSearch/Adzuna demand, or Stack Exchange interest. Missing required provenance is skipped, ambiguous known aliases are withheld, and unknown values are reported without guessing. Run with `--apply` only after reviewing the dry-run counts. Updates touch only `history_type`; records are not deleted. Production Firestore reconciliation remains pending until run by an authorized operator and its output is retained with the deployment audit.

### Onboarding and company relationship persistence

Individual onboarding remains in `users/{uid}.profile` and keeps its existing API. Employee and Company Admin answers are preserved under `profile.employee_onboarding_answers` / `profile.company_onboarding_answers` for compatibility, while deterministic normalized fields are stored in `profile.employee` / `profile.company`. `onboarding_schema_version` currently identifies canonical schema version 1. Role onboarding profile reads backfill these canonical maps from stored question answers without removing the original answers. Employee-entered employer/team names are claims, never membership proof; only backend `company_id` and `company_connection` establish a connection. Company membership invitations live in `company_invitations` with a token hash, expiry, status and intended email. Join requests live under `companies/{company_id}/connection_requests/{employee_uid}` and owner-approved memberships under `companies/{company_id}/members/{employee_uid}`. Approval/decline is an authenticated company-owner action; approval is transactionally linked to the employee account, while decline leaves the employee independent.

The shared conversational workforce-intelligence capability reads only the authenticated company's active connected member records and matching `users/{uid}.profile.employee` fields. It excludes stale, disconnected, cross-company, and internally inconsistent links. `current_skill_domains`, `self_reported_skill_confidence`, and `current_role_id` are employee onboarding inputs, not validated assessments or confirmed job assignments; aggregates omit employee identifiers. Company `critical_skill_domains` are owner-declared priorities, not role requirements. An exact registered-skill-ID/label comparison can report which declared priority labels do not appear in retrieved employee skill records, but that is not a finding that the company has a skill gap. Schemas support these fields, but repository fixtures do not establish that production companies have populated them; absent records yield insufficient data. Company-wide aggregation is limited to the verified owner/admin portal; employee portal access to company-wide aggregates is denied.

What-if simulation remains unavailable. There is no approved engine or reproducible calculation method, verified workforce baseline, validated employee-to-role assignment set, trustworthy proficiency data, approved future role-skill requirements, or documented action assumptions. The shared answer path emits no simulation facts, evidence, or projections.

### Read API and data-status contract

| Route | Method | Access | Request / response | Source and state behavior |
|---|---|---|---|---|
| `/api/v1/health` | GET | Public | no request model / health object | Process health only; no intelligence claim |
| `/api/v1/auth/me` | GET | Firebase auth | ID token / authenticated profile | Auth token and own user record |
| `/api/v1/auth/sync` | POST | Firebase auth | `AuthSyncRequest` / `AuthSyncResponse` | Own `users/{uid}` document; client cannot establish company membership |
| `/api/v1/onboarding/individual/profile` | GET | Firebase auth | none / `IndividualProfileResponse` | Own Firestore user profile |
| `/api/v1/onboarding/individual/progress` | GET | Firebase auth | none / progress | Own Firestore onboarding state |
| `/api/v1/onboarding/individual/step/{step_number}` | PUT | Firebase auth | `OnboardingStepRequest` / `OnboardingStepResponse` | Own Firestore profile; validation failures are HTTP 422 |
| `/api/v1/onboarding/{employee\|company}/profile` | GET | Firebase auth + matching account type | none / `RoleOnboardingProfileResponse` | Own user document; canonical `profile` plus legacy-compatible answers |
| `/api/v1/onboarding/{employee\|company}/step/{step_number}` | PUT | Firebase auth + matching account type | `RoleOnboardingStepRequest` / role profile | Own Firestore profile; step/question mismatch HTTP 422 |
| `/api/v1/skills/my` | GET, PUT | Firebase auth + individual | skill payload / `UserSkillsResponse` | Own Firestore profile |
| `/api/v1/skills/intelligence` | GET | Firebase auth + individual | skill/location/range filters / `SkillIntelligenceResponse` | Firestore only; unsupported ranges HTTP 422 `error_code=invalid_filter`; insufficient series returns explicit state, not a fabricated zero trend |
| `/api/v1/market/jobs` | GET | Public | query/country / `JobSearchResponse` | Stored Firestore `jobs` only; no provider call; empty/unavailable states are explicit |
| `/api/v1/company-relationships/invitations` | POST | Firebase auth + verified company owner | invitation model / created token once | Firestore invitation with hashed token; raw token returned only at creation |
| `/api/v1/company-relationships/invitations/{accept,decline}` | POST | Firebase auth + verified email | token model / status | Firestore; expired/used/wrong-email token rejected; single-use transaction |
| `/api/v1/company-relationships/connection-requests` | POST | Firebase auth + employee profile | company ID / request state | Firestore employee and company records |
| `/api/v1/company-relationships/connection-requests/{employee_uid}` | PUT | Firebase auth + owning company admin | approve/decline / review response | Firestore transaction; cross-company and self-review denied |
| `/api/v1/company-relationships/independent` | PUT | Firebase auth + employee profile | none / connection state | Own Firestore user record |

No HTTP collection route is exposed. `fetch_runs` and `skill_market_signals` are Firestore-backed; API intelligence does not fall back to SQLite. Data-state vocabulary is not yet unified across all APIs: Skill Intelligence reports insufficient/pending states, while the jobs endpoint distinguishes stored-data availability. A complete cross-domain `fresh/stale/building` contract remains future work; clients must not infer missing values as zero or real-time freshness.

Provider credentials and timeouts are read through backend settings. Keep real credentials in the untracked `.env`; do not place them in frontend configuration or logs. The example file contains placeholders only. `CORS_ALLOWED_ORIGINS` defaults to local port 3000 and should be set to the deployed frontend origin in production.

Provider field retention for scheduled job snapshots:

| Provider field | Normalized `Job` field | Firestore `jobs/{source}:{provider_id}` field | `/api/v1/market/jobs` field |
|---|---|---|---|
| JSearch `employer_name` | `company_name` | `company_name` | `company_name` |
| JSearch `job_title` | `title` | `title` | `title` |
| JSearch `job_city` / `job_state` / `job_country` | `city` / `region` / `country`; assembled `location`; request country retained as `country_code` | same | same |
| JSearch `job_category` | `category` or null when absent | `category` | `category` |
| JSearch `job_apply_link` / `job_google_link` | `source_url` | `source_url` | `source_url` |
| JSearch provider posting date fields | `posted_at` | `posted_at` | `posted_at` |
| JSearch `job_id` / `job_uid` | `job_id` | `job_id`, `source_job_id` | `job_id` |
| Adzuna `company.display_name` / `title` | `company_name` / `title` | same | same |
| Adzuna `location.display_name`/`area` / `country` | full `location` / `country_code`; distinct city and region remain null unless directly supplied | same | same |
| Adzuna `category.label` / `redirect_url` / `created` | `category` / `source_url` / `posted_at` | same | same |
| Adzuna `id` | `job_id`; absent IDs are not written as jobs | `job_id`, `source_job_id` | same |

Run backend tests with `.\.venv\Scripts\python.exe -m pytest -q`. Provider tests use mocked HTTP responses and do not call live external APIs or require API keys.

Firestore unit tests should inject the explicit in-memory demo client; its records are marked `data_origin=demo` and are not production observations. Firestore emulator integration tests are marked `integration` and skip unless both `RUN_LIVE_FIRESTORE_TESTS=1` and `FIRESTORE_EMULATOR_HOST` are set. Optional reference-data integration tests skip with a reason when the local SQLite database or staged dataset is absent.
