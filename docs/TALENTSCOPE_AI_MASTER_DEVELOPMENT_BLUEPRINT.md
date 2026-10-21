# TalentScope.ai — Master AI, Data, and Product Development Blueprint

**Status:** implementation blueprint from static source inspection and prior AI-0 through AI-2A assessments. **No production or external system was accessed.** This document describes repository code separately from local-data evidence and unknown deployed state. It does not authorize collection, migration, training, or deployment.

## 1. Executive summary and readiness decision

TalentScope.ai has a React/JavaScript client and a Python FastAPI backend. Firebase Authentication supplies identity; backend Firebase Admin code verifies tokens and Firestore is the application's configured persistence layer. SQLite is used for local reference imports and a legacy market store. Backend provider adapters and Gemini explanation are optional integration boundaries. The right direction is to retain this architecture and finish the evidence/data contract and deterministic engines before fitting predictive models.

The repository contains meaningful reusable infrastructure: typed observation models, stable IDs, per-provider collection runs, raw response archive abstraction, quality/comparability and period validation, readiness/capability registries, evidence retrieval, deterministic analytics, API response models, authorization helpers, and isolated unit tests. This is not equivalent to end-to-end product readiness. Several UI surfaces contain illustrative content; code-level handler availability does not establish adequate data, deployed rules, operational limits, provider rights, or accuracy.

**Decision:** proceed with offline contract/test hardening and approved reference/snapshot import validation. Keep external collection separately authorized. Demand forecasting is blocked until a genuine, comparable demand series meets the fixed 24 consecutive completed monthly observation threshold and beats/evaluates against seasonal-naive on a chronological holdout. Skill Half-Life is blocked until at least 36 consecutive normalized monthly observations support statistically significant decline. Production dataset coverage, Firestore rules, usage, scheduler state, and provider permission/retention are unknown. No model training is authorized by this blueprint.

### Evidence labels used below

- **Code:** directly visible in checked-out source or repository configuration.
- **Prior local assessment:** AI-1B/AI-1C/AI-2A report findings; not a claim about production.
- **Unknown:** requires an owner-approved operational check or dataset.
- **Recommendation:** proposed future behavior, not a claim that it exists now.

The prior reports are consolidated in [AI-2A architecture audit](AI_2A_ARCHITECTURE_AUDIT.md). The prior AI-1A audit accepts explicitly supplied CSV, JSON/JSONL, and canonical SQLite input and blocks unsupported native Firestore export formats. AI-1B found no approved nonempty local observation snapshot; a local SQLite observation table was empty. This says nothing about production Firestore.

## 2. Product domains and feature inventory

Status terms: **Implemented** means a code path and contract exist; **Partial** means a path exists but data, integration, or validation is limited; **Illustrative** means UI/demo calculations are explicitly not production findings; **Blocked** means essential approved data or owner evidence is missing. These statuses do not certify deployed state.

| Feature / user problem | Users and required data (authoritative source) | Existing path/engine and intended calculation | Output, validation, insufficient-data behavior, status and missing work |
|---|---|---|---|
| Individual onboarding/profile: capture career context | Individual; self-declared profile/education/experience/preferences from authenticated user | `/api/v1/onboarding/individual/*`, `/api/v1/onboarding/{user_type}/*`; onboarding service persists in `users/{uid}` | Profile/progress response. Validate schema, ownership, step completeness. Empty fields should remain unknown. **Implemented** contracts; verify field semantics, retention and deployed authorization. |
| Skills/proficiency/evidence | Individual/employee; declared skills from user, assessed evidence only from separately approved assessment source | `/api/v1/skills/my`, `/favourites`, skill service; canonical skill registry and evidence service | Skills/favourites and provenance evidence. Mark self-reported versus assessed. **Partial**: registry and storage exist; broad, independently assessed proficiency and evidence sources are not established. |
| Skill Intelligence dashboard | Individual/company; observations from `skill_market_signals`, profile skills from `users` | `/api/v1/skills/intelligence`, `/api/v1/intelligence/core`; aggregation, catalog, quality and evidence services | Trends/health with source, signal, period and evidence. Validate comparability, completeness and freshness. Return `insufficient_history`/`partial` without a chart-implied signal. **Partial**, depends on usable local/production observations (unknown). |
| Skill Demand Trends / velocity | Individual, analyst; same source-specific observation series | Execution orchestrator trend handler; Theil–Sen and established period validator | Slope/velocity and direction over comparable completed months. Validate consecutive periods, panel, unit, geography, denominator; retain four-month minimum where contract applies. **Engine implemented; coverage blocked/unknown.** |
| Skill Health | Individual; normalized share plus valid positive denominator | Health service and readiness contract | Relative momentum category/score, explicitly not absolute demand or career success. Four consecutive completed months and positive denominator. **Partial** pending eligible series and explanation/UX. |
| Skill Half-Life / relevance decay | Individual; one normalized signal family/panel per canonical skill | Half-life handler and statistical decline analysis | Estimated decay and uncertainty only when ≥36 consecutive normalized months and statistically supported decline. Otherwise report blocked with reasons. **Blocked by data.** |
| Future skill forecasting | Individuals and planners; genuine monthly comparable hiring-demand history | Forecast handler/readiness, baseline and forecast contracts | Forecast interval and provenance only after ≥24 consecutive comparable completed monthly periods and chronological holdout versus seasonal-naive. Do not call a point estimate “future demand” without evaluation. **Blocked by data; do not train yet.** |
| Skill gap and role fit | Individual; declared/assessed skill profile plus versioned role requirements from an authoritative role catalog | `skill_gap_role_fit` and action recommendation handler; transparent weighted/rule comparison | Missing/overlapping skills and explainable heuristic fit, with source and self-report label. Validate sensitivity to missing skills/weights and compare to human review. **Partial heuristic**; no validated hiring-success prediction. |
| Career opportunities/job search | Individual; stored job documents and local occupation crosswalk | `/api/v1/market/jobs` is stored-only; `/api/v1/intelligence/job`/answer routes orchestrate search/retrieval; O*NET crosswalk | Relevant postings and occupation context with fetch time. Empty/stale store must say unavailable; source terms and freshness policy required. **Partial**: current search path exists; UI also has sample/demo content, not live verified market. |
| Learning roadmap/progress/next action | Individual/employee; declared gaps, role requirements, approved learning catalog/progress | Learning page plus action/learning recommendation builder | Ordered learning actions with reasons; distinguish sample lessons from linked/available content. Validate against user goals and explicit rules. **Partial/illustrative**; no authoritative broad course corpus or progress API established here. |
| AI Assistant and conversation | Individual, employee, company; authenticated prompt, tenant-scoped data, deterministic engine evidence | `/intelligence/plan`, `/answer`, `/core`, `/actions`, `/conversations*`; planner/orchestrator and optional Gemini explanation | Typed answer plus facts/evidence, readiness, limitations; persist conversations. Validate route, authorization, claims against facts; no evidence means no asserted live finding. **Partial**: orchestration exists, runtime data and Gemini availability unknown. |
| Favorites/settings/notifications | Individual/employee; user preferences and notification events | Skills/market favourites persist under user; settings screens | Preference state. **Partial**: favorites APIs exist; no complete notification/event delivery service is demonstrated. |
| Public company discovery | Individual/employee; approved company directory / company records | `/api/v1/company-relationships/companies`; bounded active-company query | Matching public directory entries. Validate public-field minimization and tenant exposure. **Partial**; actual directory coverage and privacy policy unknown. |
| Company registration/admin/employee relationship | Company admin/employee; authenticated user, company, membership, invitations/requests | `/api/v1/company-relationships/*`, company relationship service and membership dependency | Membership/invitation state. Transactional state transitions and trusted membership checks exist in code. **Implemented path; deployed rules/data integrity unknown.** |
| Workforce inventory | Company admin; membership-scoped `companies`, `members`, `users` declared skills/roles | `CompanyWorkforceStore`, company intelligence handler; bounded members read | Aggregated declared skills/roles. Label declarations, avoid employee-level leakage and small-cohort re-identification. **Partial**; not verified assessment or representative census; owner must set cohort thresholds. |
| Target role/skill requirements and workforce gap | Company admin; versioned current/target role definitions, authorized workforce profile | Company intelligence/action routes, currently partial stored-workforce context | Role/skill gap and evidence-linked options. Validate catalog authority, completeness, weights and cohort sufficiency. **Partial**; authoritative target demand and assessed skill inputs remain missing. |
| Internal mobility/upskill/reskill/redeploy/hire/track | Company admin and employee; role requirements, workforce profile, learning catalog, approved demand evidence | Action recommendation engine, company/employee assistant | Ranked actions with rationale, cost/constraints only when supplied. Validate with users and outcome tracking. **Partial**; persistent action tracking API is not established, recommendations are heuristic. |
| Workforce market alignment | Company admin; validated company skill inventory and comparable market observations | Company context and market intelligence engine | Evidence-matched gaps, with source coverage and panel caveats. **Partial/blocked** by inventory completeness and market series. |
| Workforce what-if simulation | Company planner; explicit headcount/skills/constraints/cost assumptions | UI `WorkforceSimulation.js` explicitly states its figures and local arithmetic are illustrative; no connected service | Deterministic arithmetic only after requirements are specified; no predictive/causal claim. **Illustrative, not validated simulation.** |
| Company assistant/strategy | Company admin; membership-verified aggregate company facts plus evidence | Shared orchestrator with company authorization | Evidence-grounded answer without cross-tenant facts. **Partial**; source-level authorization present, runtime data sufficiency and deployed rules unknown. |
| Employee skills, company link, development, roles, AI | Employee; own profile and authorized membership; same underlying skill/role evidence | Employee pages and shared skills/relationships/intelligence routes | Own profile and scoped suggestions. **Partial**; notifications and learning completion integrations not proven. |
| AI task exposure | Planners/individuals; licensed, versioned, occupation-task exposure data with defensible method | Handler exists; capability registry marks `ai_task_exposure` blocked for `NO_LICENSED_EXPOSURE_DATASET` | No score until a licensed dataset and reproducible methodology pass validation. **Blocked by code policy and missing data.** |
| Platform search, settings, usage limits/monitoring | All; indexes, auth, quotas and operational telemetry | Catalog/entity search, Firebase token verification, Gemini budget store, read guard | Stable search and usage metrics. **Partial**: read guard metrics are in-process, not proof of centralized monitoring; quotas/config and provider rates unknown. |

Additional source/data surfaces: occupational crosswalk/reference lookup, market collection status/provider capability catalog, conversation delete/list, calculation cache, raw response archive, and explicit offline demand-series readiness audit.

## 3. Feature-to-engine-to-data map

| Domain output | Input owner/source | Engine(s) | API/UI | Gate and user-facing fallback |
|---|---|---|---|---|
| Profile and skill state | User-declared; user document | Auth/profile normalization and canonical skill resolver | onboarding/skills APIs; individual/employee profile | Unknown stays unknown; require login and owner scope. |
| Occupational context | Versioned O*NET/ESCO import | Entity resolution and crosswalk | `/intelligence/entities/resolve`, catalog/core; career | Return no-match/ambiguous rather than guessing; display taxonomy release. |
| Market snapshot | Provider-specific observations/jobs and fetch runs | Normalizer, sampling/completeness, aggregation | `/market/jobs`, `/intelligence/market` | Snapshot timestamp and sample limitations; empty/stale/partial status. |
| Trend and health | One comparable source/signal series | Validator, period gate, Theil–Sen, health metrics | `/skills/intelligence`, `/intelligence/core|answer` | Four completed consecutive comparable periods for trend/health; show exact blocker. |
| Half-life/forecast | Same-source eligible history | Normalization/statistical test; baseline forecast/evaluation | core/answer routes | 36 normalized months for half-life; 24 consecutive comparable months plus holdout baseline for demand forecast. Otherwise blocked, no fake chart. |
| Individual role fit/actions | User profile and versioned occupation/role skills | Explicit weighted deterministic rules | answer/actions; career/learning | Label heuristic/self-reported; show missing inputs and weights. |
| Company gap/actions | Authenticated company membership and declared workforce + target role source | Tenant-scoped aggregator and rules engine | core/actions; company workforce/mobility/admin | Require coverage/cohort threshold; aggregate only, show sample coverage and assumptions. |
| Explanation | Already validated response facts | Optional grounded Gemini explanation | answer/core UI | Feature disabled or quota exceeded => deterministic factual answer, no failed analytics; LLM cannot alter facts. |
| Exposure | Licensed task dataset | Versioned deterministic/validated exposure mapping | answer/capabilities | Blocked until dataset/methodology owner approval. |

## 4. Canonical data architecture

### 4.1 Observation contract

Reuse `MarketObservation`, `AggregatedMarketSignal`, `SeriesQualityReport`, `AnalyticalReadinessReport`, `FetchRun`, and `FirestoreObservationStore`; extend only by a compatibility-reviewed versioned migration when needed. Existing fields include ID, source, signal family, skill and optional canonical skill ID, value, observed timestamp, period, location/scope, unit and denominator/unit, provider posting timestamp/ID, source URL, metadata, history type, origin, fetch run, query/panel/series/extractor version, quality, confidence, count, and annotations. Existing code also enforces period/timestamp consistency and positive denominator where supplied.

Canonical required semantics (recommendation):

| Field | Rule |
|---|---|
| `observation_id` | Stable deterministic identity from source-native ID or canonical source/entity/period/metric/scope/panel identity; collision must fail if identity fields conflict. |
| `source`, `provider` | Normalized immutable source/provider key, never inferred from human-readable label. |
| `signal_type`, `metric` | Exactly one family and one metric: demand, adoption, interest, attention/context, or reference. No cross-family sum. |
| `entity_type`, canonical skill/occupation ID | Taxonomy namespace and version; unknown mapping retained as unresolved, not guessed. |
| `value`, `unit` | Finite, nonnegative if the source measure requires; unit must remain fixed within a comparable panel. |
| `denominator`, `denominator_unit`, `denominator_semantics` | Positive and defined for shares/rates; zero is permitted only when a complete sampling frame verifies a true zero. Store numerator and denominator meaning. |
| `geography`, `scope` | Normalized geography and query scope; global/remote/local are distinct. Never merge location panels silently. |
| `observed_at`, `period`, `period_grain`, `collected_at` | UTC instants plus canonical closed period; no current incomplete month as completed evidence. Separate observed and collected times. |
| `query_id`, `panel_version`, `extractor_version`, `taxonomy_version` | Immutable definitions for source query, sampling frame, transform and taxonomy mapping. Drift starts a new panel. |
| `fetch_run_id`, collection status | Link to terminal run record including counts, pagination, completeness and error class. Partial/failed run never implies zero. |
| `data_origin`, `history_type` | Distinguish approved historical backfill, platform-collected, point snapshot, static reference, demo/test. Do not mix demo/test into real evidence. |
| `provenance`, `quality` | Origin/rights/manifest and quality flags, comparability and coverage state. Keep raw provider payload out of analytics documents. |

Signal families remain separate:

1. **Hiring demand:** job postings sampled by JSearch/Adzuna or a licensed historical source. Posting counts are sampled-panel metrics, not labor-market universe counts unless proven otherwise.
2. **Developer adoption:** GitHub repository/developer activity; distinct metric and typically quarterly periodicity.
3. **Technical interest:** Stack Exchange/Hacker News/ecosystem metric. Define metric semantics per provider; not hiring demand.
4. **Attention:** Wikipedia pageviews; page attention, not employers/vacancies.
5. **Static reference:** O*NET/ESCO occupation and skill reference; versioned snapshots, not a time series of current demand.
6. **Individual declaration:** user-authored profile/skills/preferences, provenance and timestamp; not independently assessed.
7. **Company declaration:** company-provided workforce, role and priorities; completeness and reporting date must accompany aggregates.

### 4.2 Logical storage map

“Observed counts” below are deliberately **unknown**. Write/read paths are from source, not deployed config.

| Existing collection/table | Owner and class | Shape/access path from code | Preservation and policy |
|---|---|---|---|
| Firestore `users/{uid}` | User; PII/profile source | Auth sync, onboarding, skills, favorites, membership references; per-user reads/writes | Preserve; field-level privacy, retention, export/deletion. Do not treat declared skill as assessed. |
| `companies/{company_id}` | Company admin; declared org context | Company profile and workforce context | Preserve with authorization audit and reporting date. |
| `companies/{id}/members/{uid}` | Company membership authority | Membership checks and bounded workforce listing | Preserve selectively; reconcile before migration; strict tenant boundaries. |
| `companies/{id}/connection_requests/{uid}` | Employee/admin workflow | Transactional request/review | Preserve current state/history if needed for legal/audit policy. |
| `company_invitations` | Company relationship service | Hashed invitation token lookup, bounded list | Preserve/revoke per lifecycle; no plaintext token migration. |
| `skill_market_signals` | Data platform; canonical source observations | Stable IDs; targeted skill/series/source/time queries; batch set (450 writes per batch in code); query result max 2,000 plus probe and TTL cache | Preserve provenance; validate and quarantine. Do not wholesale reset. |
| `fetch_runs` | Collection operations | Run create/update/get/latest and bounded summary (source shows 500 limit) | Preserve operational provenance and failures; TTL cache is not authoritative. |
| `raw_response_archives/{id}/chunks/{id}` | Collection/security owner; raw payload | Archive metadata/chunks; index override disables `payload_bytes` indexing | Restricted access/short retention under provider terms; raw archive is not an analytical source. |
| `jobs` | Market data owner; sampled posting records | Stored JSearch reads; query by country/fetched time indexes; collection writes | Preserve only per provider terms; deduplicate/version; expire per retention; not historical series. |
| `calculation_records` | Analytics; derived cache/evidence | Targeted ID reads and evidence references; in-process cache | Rebuildable, versioned and invalidated against evidence; preserve lineage when useful. |
| `intelligence_conversations` | User/company; user-generated content | Per-conversation doc, owner/company-scoped list/get/delete; API list cap 100 | Retention/deletion policy needed; protect message and answer payloads. |
| `gemini_usage_budgets` | Platform ops; quota metadata | Transaction reservations: global/day, global/minute, user/hour keys with expiries | TTL/cleanup policy; never interpret as model evidence. Monitor contention and actual cost externally. |
| SQLite reference tables (`ref_onet_*`, `ref_esco_*`, `ref_github_*`, ingestion log) | Data steward; versioned reference | `ReferenceDataStore` and ingestion scripts | Preserve/reimport versioned source files, license, checksum, import counts. Do not assume DB file is populated/current. |
| SQLite legacy market store | Legacy/local; unclear authority | `MarketDataStore` legacy query/write paths | Leave unchanged pending offline inventory/provenance decision; never silently promote to Firestore truth. |
| Emulator fixtures | Developers; test-only | Local demo project and emulator endpoints | Disposable only in isolated local environment; never export as real data. |

### 4.3 Migration/reset recommendation

No clean start or wholesale deletion is justified by static evidence. If owners later approve a rebuild, create a versioned read-only inventory and checksums, classify records, write validated records to a new versioned namespace or staging project, run parity/count/relationship checks, and switch reads only after owner approval. Keep users, permissions, company memberships, audit provenance, and valid observations protected. Maintain rollback/read alias until acceptance; delete old data only under a separate documented retention decision. Never infer production contents from local SQLite.

## 5. Existing implementation reuse map

| Contract/module | Reuse | Known concern / next refinement |
|---|---|---|
| `backend/app/models/skill_intelligence.py:MarketObservation` | Canonical observation shape and validation | Version field and required provenance completeness should be made explicit; preserve old record compatibility deliberately. |
| `storage/observation_identity.py`, `FirestoreObservationStore` | Stable IDs, conflict detection, 450-operation batch writes, bounded reads/cache | `all_documents()` remains a broad scan guarded by warning/strict mode; enforce targeted queries in routine APIs and measure real billed reads. |
| `analytics/series_validation.py`, `observation_period.py` | Comparability dimensions and completed-period rules | Contract tests must cover query/panel/extractor/geography/unit/denominator/origin/history drift. |
| `analytics/analytical_readiness.py`, `signal_quality.py` | Existing trend/forecast input readiness | Generic internal forecast minimum defaults to 6; feature-level operational forecast gate must enforce fixed 24-month policy (do not mistake registry gate for final readiness). |
| `analytics/trend.py`, health and half-life modules | Deterministic analysis | Preserve four-month trend/health and 36-month half-life policy; uncertainty/sensitivity should accompany point estimates. |
| `capability_registry_service.py` | Global status and request readiness | `available` means handler implementation; UI must display runtime assessment and evidence gate. Registry marks skill-gap partial and AI task exposure blocked. |
| `intent_planner_service.py`, `execution_orchestrator_service.py` | Deterministic routing, domain handlers and typed response | Large orchestration module should retain a single response/evidence contract; track route/handler coverage and eliminate mismatches. |
| `evidence_service.py`, calculation store | Evidence retrieval and reusable versioned results | Ensure cache key includes every evidence/config version and stale evidence invalidates persisted results. |
| `market_collection_service.py`, provider adapters, `FetchRunStore` | Explicit collection, per-run status, pagination/quality metadata | Keep opt-in and separately authorized. Source terms, panel registry, retries/idempotency and production scheduling require owners. |
| `ConversationStore`, `LLMExplanationService` | Conversation persistence, grounded explanation, quotas/cache | Needs retention/deletion guarantees, tenant isolation tests, Gemini-disabled behavior; no external call during tests. |
| `FirestoreCompanyWorkforceStore`, authorization deps | Bounded, membership-scoped workforce reads | Declared profile values only; set minimum cohort/privacy policy and evaluate access paths under deployed rules. |
| `ReferenceDataStore` | SQLite local reference import/read | Add/check release manifests and test DB location/schema; keep separate from market source-of-truth. |
| `audit_demand_series_readiness.py` | Offline supported snapshot contract and aggregate results | Keep no-default-input behavior blocked and no raw identifiers in output; native export importer remains unsupported. |

## 6. AI engine pipeline and specifications

Pipeline: approved source → provider/source adapter → normalized typed record → identity/taxonomy resolution → quality/provenance gate → comparability and closed-period validation → canonical storage → feature engine → readiness/confidence result → calculation/evidence record → deterministic action → optional fact-bound Gemini text → typed API response → UI with freshness/status.

Each stage must fail with a machine-readable reason and preserve source evidence. No stage may convert unavailable data to zero, use synthetic history, cross tenant scope, or have Gemini supply numeric facts.

| Engine | Interface/input → output | Algorithm and validation | Failure/readiness and tests |
|---|---|---|---|
| 1. Source/observation validation | Provider record + adapter manifest → canonical observation + quality report | Strict schema, finite values, source-specific unit/denominator/period rules, idempotent stable identity; validate duplicate conflicts and completeness | Reject/quarantine invalid/partial; fixtures for malformed, duplicate, panel drift, true-zero vs absent. |
| 2. Identity/taxonomy resolution | Raw skill/role/occupation + context/version → canonical ID, candidates, confidence/reason | Existing resolver/registry exact and contextual matching; ambiguity returns candidates, no forced fuzzy match | `not_found`/`ambiguous`; tests polysemy, versioned aliases, unresolved IDs. |
| 3. Data quality/comparability | Canonical observations + source panel → `SeriesQualityReport` | Reuse `series_validation` dimensions; normalize geography and units explicitly; assess denominator, collection completeness and gaps | `incomparable`, `configuration_changed`, `incomplete`, `low_coverage`; mismatch matrix tests. |
| 4. Period/readiness | Valid series + as-of date + feature policy → completed periods and blockers | Reuse completed-month parser; trend/health ≥4, forecast generic readiness must be overridden by fixed 24 gate, half-life ≥36 | Missing/incomplete/future months block; tests boundary as-of, gaps, leap/year transitions. |
| 5. Snapshot/history aggregation | Valid rows + panel key → per-period metric and provenance | Exact dedupe, count or explicit numerator/denominator aggregation; no cross-family/provider sum without validated common frame | Partial output carries completeness flag; test repeat posts, overlap, empty-complete semantics. |
| 6. Trend/velocity | Comparable monthly series → Theil–Sen slope, direction, uncertainty/confidence | Robust median pairwise slopes; direction and percentage only with valid baseline; four consecutive months | Insufficient periods => no trend; test outliers, flat/zero baseline, scale, gaps. |
| 7. Skill Health/Half-Life | Normalized share series → relative momentum / decay estimate | Existing health method; half-life via established statistical decline and decay method, not a generic score | Health ≥4 + positive denominator; half-life ≥36 plus supported decline; tests noise/no-decline and confidence. |
| 8. Demand forecast | Genuine demand series → forecast distribution/interval and evaluation | First baseline seasonal-naive (plus last-value comparator); candidate parsimonious statistical model only after series diagnostics; never Gemini. Rolling-origin chronological holdout | ≥24 consecutive comparable closed months and baseline holdout evaluation; block missing data/weak baseline. Test leakage, naive equality, horizon, metrics. |
| 9. Skill gap/role fit | Versioned role requirements + declared/assessed profile → coverage/gap and rationale | Deterministic weighted overlap, proficiency normalization; absent skill is unknown vs explicit not-present; separate source trust | Report heuristic and missingness; tests weight changes, missing profile, assessment-vs-declaration. No hiring probability. |
| 10. Recommendation/actions | Validated gaps, evidence, constraints → ranked action candidates | Rules/weighted score with reason, evidence refs, limitations; no LLM ranking of facts | Return no action if insufficient evidence; persistence/tracking API is a separate product requirement. Test evidence IDs, determinism, duplicates. |
| 11. Company workforce analysis | Authorized member/profile snapshot + requirements → privacy-safe aggregates/gaps | Tenant membership check first, bounded reads, count skill coverage, report denominator and as-of; minimum cohort threshold owner-set | Incomplete sample/low cohort => suppress or label; tests cross-tenant, partial members, small cohort and self-report. |
| 12. Workforce scenario calculator | User-approved baseline + explicit scenario inputs → transparent arithmetic deltas | Deterministic headcount/skill/cost equations with documented constraints; no causal/predictive inference | Currently UI-only illustrative demo. Gate until approved inputs, formulas, validation and API exist; property/bounds tests. |
| 13. Assistant orchestration | Authenticated query + portal + verified scope → plan, engine result, answer contract | Existing planner/capability registry/orchestrator; authorize before retrieval; attach facts/evidence; LLM only paraphrases grounded facts | Capability blocked/insufficient => status + next data needed. Test fake Gemini transport only if isolated; never rely on LLM for routing/metrics. |
| 14. AI task exposure | Licensed occupation-task data + method/version → exposure estimate | No method recommended until licensed source and methodology review; do not substitute public anecdotes | Registry is correctly blocked (`NO_LICENSED_EXPOSURE_DATASET`); tests ensure blocked response and no fabricated score. |

## 7. Model and analytics decision matrix

| Target | Candidate and baseline | Data/evaluation | Build decision / limitations |
|---|---|---|---|
| Trend direction | Theil–Sen; baseline: endpoint change/flat trend | ≥4 consecutive comparable completed monthly observations; sensitivity to outliers and panel drift | Engine can be used now on eligible data; not a forecast or causal claim. |
| Relative Skill Health | Existing normalized momentum rule; baseline: no change | ≥4 completed periods and positive valid denominator; sensitivity and formula tests | Implement deterministic explanation/UI now; score is relative signal only. |
| Skill Half-Life | Existing normalized decline/decay estimator; baseline: no decline | ≥36 consecutive normalized months; test uncertainty and statistical support on genuine series | Remains blocked absent data; do not fit on synthetic fixture as evidence. |
| Demand forecasting | Seasonal-naive primary baseline, last value secondary; candidate simple seasonal/statistical model if diagnostics justify | ≥24 consecutive comparable completed monthly observations; chronological holdout/rolling origin; MAE, MASE or scaled error, interval coverage and bias vs seasonal-naive | Block training/claims until real panel and holdout; no universal target accuracy promised. |
| Role fit | Transparent weighted deterministic rules; baseline: unweighted overlap | Role catalog version, profile completeness, held-out expert review or user acceptance | Can implement/test on labeled fixtures; heuristic only, not job success. |
| Recommendations | Deterministic rules/evidence ranking; baseline: sorted uncovered requirements | Evidence coverage and user feedback/outcome tracking; audit reason reproducibility | Partial implementation. LLM may explain only. |
| Workforce gaps | Aggregate counts/coverage rules; baseline: current declared inventory | Tenant-scoped cohort, denominator coverage, role requirement version; validate with company owner | Build after privacy thresholds and trusted completeness policy. |
| Workforce simulation | Transparent deterministic scenario arithmetic; baseline current state | Explicit constraints/cost assumptions, expert review, boundary/property tests | UI currently says illustrative; no empirical forecasts/causality. |
| AI exposure | No candidate until licensed task dataset/method chosen | Dataset rights, task/occupation mapping, temporal validity, external validation | Blocked by missing approved dataset. |
| LLM explanation | Gemini optional text only | Facts/evidence provided to model; claim validation and disabled/quota paths | Do not benchmark as analytics model; no LLM-supplied numeric forecast. |

Metrics never establish production utility from test fixtures. Forecast holdout must be chronological, not random. Keep untouched evaluation windows; report metrics by panel and baseline, uncertainty, coverage and limitations.

## 8. Historical data acquisition and collection plan

### Source-specific options

| Source | What it measures | Acquisition path and limitation |
|---|---|---|
| JSearch | Sampled job postings per query/location/time | Confirm terms, retention, page limits, query stability and historical/backfill permission with provider owner. Existing adapter tracks requested pages/provider totals/coverage; not a full labor census. |
| Adzuna | Sampled postings with source/geography query semantics | Confirm commercial rights, API limits and geography; preserve its sampling panel separately from JSearch. |
| Licensed historical posting dataset | Potential genuine backfill, depending on rights | Preferred only if license permits retention/analytics, timestamp granularity and vacancy dedupe are adequate, and provenance manifest is supplied. No such dataset was identified locally. |
| GitHub Innovation Graph | Repository/developer activity, generally quarterly | Keep adoption family and native period grain; cannot fill monthly job demand. Record version, geography and metric. |
| Stack Exchange/HN/ecosystem | Technical attention/activity according to endpoint | Treat as independent interest/adoption proxies; owner confirms terms and source-specific denominator. |
| Wikipedia | Pageviews | Attention only. Do not represent as hiring evidence. |
| O*NET/ESCO | Occupation/skill reference and relationships | Versioned local import; record license/release/checksum/ingestion counts. Static baseline, not job-demand time series. |

No approved historical snapshot was found in prior local assessment. Exact next data input: an owner-approved, minimized, canonical observation snapshot (CSV, JSON/JSONL, or supported SQLite schema) plus manifest specifying source/license, time range, export method, schema and panel version, checksum, redaction, approval, units, denominator, geography, query, and run completeness. Do not reinterpret native Firestore export artifacts as one of these formats.

If no licensed backfill is available, future prospective collection is a separately approved project: choose fixed query/geography/panel, document denominator and coverage, schedule only after approval, persist terminal run state including partial/failure, deduplicate source-native reposts by policy, mark panel drift, and close periods only after completeness checks. Each successful completed month adds one observed period; failed or missing month stays missing. Earliest threshold is 24 completed consecutive months after approved collection begins (or 36 for Half-Life), plus holdout/test and quality work; no calendar date is promised and 24 months is not a guarantee of readiness.

## 9. Firestore cost, access, privacy, and operations

**Existing source controls:** observation store targets IDs and has 60-second per-instance query cache; broad scans call `FirestoreReadGuard`; strict scan blocking is controlled by an environment variable. It caps observation queries at 2,000 plus one probe. Observation insertion deduplicates IDs and batches new docs in groups of 450. Fetch-run summaries are bounded and cached. Company workforce read limits members. Conversation listing API caps at 100. Index configuration covers job country/fetched time and observation skill/series/signal with observed time; raw archive payload bytes are unindexed. These are code/config facts, not deployed usage or cost evidence.

**Recommended controls:**

- Keep observations shared by source and panel; never copy market series per user. Store only small, versioned prepared aggregates if their evidence IDs and invalidation keys are explicit.
- Key calculation cache by engine/formula version, source, signal, entity, geography, panel, query, unit, denominator, period window, origin and observation evidence digest. Re-read/validate source evidence before reuse or use a documented freshness policy.
- Add pagination/cursors and bounded time ranges to user-facing history endpoints. Make broad scans unavailable in normal API paths; strict guard should fail CI and production read tests.
- Measure actual document reads, writes, index/storage growth, latency, cache hit, retries, query cardinality and provider runs. The current in-process read guard is not durable or fleet-wide monitoring.
- Use idempotent run/document keys, bounded retry with backoff, transactional quota reservations, and explicit partial status. Avoid repeated read-before-write if deterministic create/update semantics can safely reduce reads.
- Review index exemptions and composite indexes against exact query plans; deploy index changes through owner-reviewed config. `firestore.json`/`firestore.indexes.json` do not establish deployed state.
- Set retention and access for raw payloads, job postings, conversations, profile data and quotas; apply deletion/export requests and least-privilege service identity. Restrict raw provider archives from user-facing APIs.
- Enforce auth before data access. Verify token revocation, user ownership, company membership and role on every path. Firestore rules/deployed IAM are unknown; owner must audit them.
- Monitor Gemini/provider quotas, errors and usage from project-owned dashboards; do not invent pricing, quotas, or current usage from repository settings.

**Owner verification required:** deployed project/environment IDs (do not disclose credentials), Firebase rules/IAM and indexes, scheduled jobs, Firestore usage/billing metrics, provider quotas/terms, retention/TTL setup, and any production counts/quality. No live counts are asserted here.

## 10. Frontend/backend endpoint and response matrix

All listed backend API routes are mounted beneath `/api/v1`. `get_current_user` protects most routes with Firebase bearer-token verification. `/market/jobs` is source-defined as stored-only and does not require `get_current_user` in the route. Responses should carry stable state, freshness, source/panel and evidence where the model supports it; UI must distinguish empty, unavailable, partial, stale, insufficient history and blocked. Exact request/response Pydantic schemas are those in `backend/app/models`; do not introduce parallel untyped frontend calculations for market findings.

| Method/path | Auth/scope | Data/engine and consumer | Fallback/status contract |
|---|---|---|---|
| `GET /health` | Health only | API availability; platform shell | Health is not dependency readiness. |
| `GET /auth/me`, `POST /auth/sync` | Firebase user | Token verification/profile sync; app shell | 401 invalid token; safe generic sync error. |
| `GET /onboarding/individual/profile`, `/progress`; `PUT /onboarding/individual/step/{n}` | User-owned | User profile; onboarding | Schema validation, incomplete steps represented explicitly. |
| `GET/PUT /onboarding/{user_type}/profile`, `/step/{n}` | User-owned; supported role type | Role onboarding | Validate type/step; no assumed complete profile. |
| `GET/PUT /skills/my`, `/skills/favourites` | User-owned | Declared skills/preferences; profile/settings | Empty list is valid, not market signal. |
| `GET /skills/intelligence` | User-owned | Stored observations, analytics; skill dashboard | Invalid filter 422; unavailable/insufficient state; do not draw invented series. |
| `GET /skills/intelligence/{skill_id}/evidence` | Authenticated; market evidence | Evidence service; evidence panel | 404 unknown skill; include source/period/provenance, no raw payload. |
| `GET /market/jobs?query=&country=` | Route has no user dependency | Stored JSearch job docs; career/jobs | `available`, `empty`, or `unavailable`; fetched timestamp. Note public endpoint requires owner security review/rate limit. |
| `POST /market/admin/collect` | Firebase admin claim | Explicit provider collection + Firestore writes | Admin only; terminal per-provider run; disabled providers and partial/failure status. Never auto-trigger from UI view. |
| `GET /market/status`, `/collection/status`, `/capabilities` | User for status; capability route no explicit dependency | Fetch runs/provider capability metadata | Status reflects recorded run only, not freshness guarantee; inspect route auth on public capability metadata. |
| `GET /intelligence/catalog/skills`, `/catalog/market`; `PUT /catalog/market/favourites` | Authenticated | Taxonomy, observations, jobs/employer list, user favorite | Catalog reference status separate from live market signal state. |
| `POST /intelligence/plan`, `/answer`, `/core`, `/actions` | Authenticated; company/employee membership verified for those portal types | Planner, orchestration, deterministic engines, evidence, optional Gemini | Preserve typed response/readiness/limitations; reject caller-provided observations; 403 unauthorized company. |
| `GET /intelligence/capabilities`; `POST /capabilities/evaluate`, `/entities/resolve` | Authenticated | Registry evaluation/entity mapping | Distinguish global handler status from request data readiness; blocked/ambiguous status. |
| `GET /intelligence/skill`, `/market`, `/job` | Authenticated and portal scoped | Convenience query into shared Core Intelligence | Validate range, return same readiness/provenance semantics as core. |
| `POST/GET /intelligence/conversations`, `GET/DELETE /{id}` | Authenticated owner; company membership when portal supplied | Conversation persistence | 404 when missing/inaccessible; bounded list (≤100); deletion should honor retention contract. |
| `GET /company-relationships/companies`; invitation/connection POST/GET/PUT; `/independent` | Authenticated user/admin and membership checks per operation | Company relationship service | 403/404 generic to avoid enumeration; state transition and audit log. |

**Frontend consumers:** `core-intelligence-client.js` is the shared intelligence API wrapper; catalog client handles catalogs; `skills-api.js`, `onboarding-api.js`, `auth-api.js`, and company-relationships API wrap domain contracts. Individual/employee/company pages consume these wrappers variably; career and learning still include explicit illustrative/demo content; company simulation explicitly labels local figures as illustrative. Before production release, trace every visible chart/card to its source API and ensure no sample/demo object is rendered as a real finding.

## 11. Test strategy and acceptance criteria

| Layer | Required focused coverage | Acceptance criterion |
|---|---|---|
| Models/validation | finite/negative values, unit/denominator, timestamp/period, identity collision, canonical mapping | Invalid record rejected with safe reason; no silent coercion to zero. |
| Quality/comparability | source/signal/panel/query/geography/unit/denominator/extractor/origin mismatch | Each incompatible dimension blocks merge and returns structured blocker. |
| Period/readiness | duplicate/missing/future/incomplete months, completed-month boundary, 4/24/36 thresholds | Threshold boundaries exact; missing period never interpolated. |
| Demand aggregation | duplicate/repost, pagination truncated, partial run, source overlap, true zero | Complete zero distinguished from no data; provenance preserved. |
| Analytics | outliers, zero baseline, positive denominator, no-decline, statistically supported decline | Deterministic outputs and uncertainty; no claims below required gate. |
| Forecast | seasonal-naive, chronological holdout/rolling-origin, leakage, baseline tie/worse/better | Model only eligible if holdout evaluated against baseline; no random time split. |
| Role fit/actions | absent vs not-present, skill source confidence, weights, missing requirements | Explainable deterministic result; user can see heuristic/self-report status. |
| Company access | cross-company UID/company spoof, employee/admin roles, small cohorts, partial member reads | No cross-tenant data; cohort privacy rule applied. |
| Storage | isolated fake Firestore/emulator only, query bounds, batch limits, cache invalidation, idempotent retries | No live SDK initialized; bounded reads and evidence-version cache invalidation verified. |
| API/frontend | Pydantic schema, 401/403/404/422, blocked/partial/stale/empty states, wrappers/screens | Every market figure maps to response evidence/freshness; illustrative content visibly marked. |
| LLM | Gemini disabled, quota exhausted, timeout, ungrounded numeric claim, prompt injection | Deterministic answer remains; unsupported claim rejected; no network in unit tests. |
| Ops/cost | query/read budget tests and metrics emission | Regression limits configured by owner from measured workload; never invent project quotas. |

Synthetic fixtures are permitted for deterministic unit behavior only and must be clearly test-only. They never count toward readiness. Add tests only with a specific contract change; this blueprint itself changes no runtime code. No tests were run for this documentation deliverable.

## 12. Preservation and migration recommendations

- **Preserve:** user accounts/profile/skills and authorization relationships subject to verified ownership/legal retention; valid observations and fetch-run provenance; licensed reference dataset/version manifests.
- **Validate/quarantine:** observations with missing/contradictory units, source/panel, time, denominator or provenance; company membership inconsistencies; stale calculations; legacy market SQLite whose authority is unclear.
- **Restricted retention:** raw provider archive, job content and conversations under privacy and provider terms. Separate purpose-limited retention/deletion decisions.
- **Rebuildable:** calculation cache, aggregates and quotas where owner/accounting policy permits. Recompute from validated primary observations with versioned calculation IDs.
- **Leave unchanged now:** all production data, all existing local databases, existing uncommitted working-tree changes. No reset is justified.

Any approved migration uses inventory/checksum → versioned staging → schema and provenance validation → access/relationship parity → shadow reads → owner acceptance → reversible read switch → separately approved retention cleanup. Preserve rollback and audit trail. Never mass-delete or transform in-place as part of a model rebuild.

## 13. Prioritized implementation roadmap and completion criteria

| Stage | Work and dependency | Completion criteria |
|---|---|---|
| 0. Owner evidence/decisions | Establish data owners, licensed source rights, deployed auth/rules/index review, privacy/retention, company simulation scope; no credentials shared | Written decisions and approved minimized snapshot/manifest or explicit prospective-only plan. |
| 1. Canonical contracts | Reconcile observation/model fields, source panels, taxonomy versions and state vocabulary; preserve compatibility | Contract docs + migrations reviewed; no signal-family conflation; schemas reject missing semantics. |
| 2. Offline fixtures/tests | Unit fixture packs for source schemas, identity, comparability, periods, completeness, tenant scope | Isolated tests prove key acceptance and blockers; fixtures explicitly synthetic/test-only. |
| 3. Data import/readiness | Use existing audit importer only for supported files, read-only; reconcile reference SQLite separately | Aggregate import report, checksum/manifest, quarantine reasons; no raw personal data in report. |
| 4. Collection foundation | Only after separate owner approval: source adapter/panel registry, run lifecycle, idempotency, pagination, monitoring | Provider terms approved; complete/partial/failure state; reproducible panel; safe rate limits and retention. |
| 5. Deterministic engines | Entity/quality/period/trend/health/role-fit/actions; each consumes validated types | Unit/property tests and API schemas; source evidence in all results; safe insufficient-data fallback. |
| 6. Forecast evaluation | Accumulate approved consecutive history; seasonal-naive chronological holdout; candidate comparison | Fixed 24-month gate plus documented holdout metrics and baseline comparison; independent review before model selection. |
| 7. Assistant grounding | Route by planner/capability; authorize before reads; attach evidence; optional explanation after output validation | Gemini-disabled path works; no model-origin numerical facts; claim validation and quota tests pass. |
| 8. Company workforce/simulation | Define cohort/privacy policy, target-role source, cost assumptions; connect workforce endpoint; keep calculator deterministic | Tenant isolation and small cohort tests; source/denominator clarity; simulation formulas reviewed and UI avoids forecast claim. |
| 9. Frontend integration | Map each card/chart to endpoint and typed state; remove or label all demo data; freshness/evidence UX | Contract tests; blocked/partial/stale states; no fabricated live values. |
| 10. Emulator/deployment readiness | Only local emulator with explicit demo config, then owner-controlled staging and production approvals | No live endpoint in local tests; rule/index reviews; monitoring, rollback, retention and incident process approved. |

Each stage gates the next: model choice depends on validated time series; company decisions depend on trusted tenant data; UI claims depend on engine readiness; deploy depends on security/rules/operational owner approval.

## 14. Missing evidence and owner decisions

1. **Firebase incident:** the earlier accidental Auth user-list request and its outcome are not established by repository source. Firebase project owner/security team must review appropriate Auth audit/activity records and access logs for the incident time/project using their approved process and decide response. This blueprint did not inspect those records or claim they were checked.
2. **Production state:** owner must verify actual Firestore project, rule set/IAM, indexes, scheduled jobs, collection counts, retention, Firestore read/write usage and deployed backend config. No live state can be inferred here.
3. **Data rights:** provider/legal owner must approve source-specific historical collection/backfill, retention, redistribution and sampling methodology.
4. **Dataset:** data steward must provide approved snapshot plus manifest or confirm prospective collection; historical coverage remains unknown in production.
5. **Privacy:** define raw archive, job-posting, conversation and profile retention/deletion; set minimum cohort sizes and employee consent/notice.
6. **Role standards:** identify authoritative versioned role/skill requirements and whether any proficiency is assessed versus self-reported.
7. **Simulation:** owner chooses whether feature is illustrative arithmetic or production scenario tool and supplies explicit constraints/cost and validation requirements.
8. **Task exposure:** license and approve dataset/methodology before unblocking; until then keep capability blocked.
9. **Operational budgets:** use Firebase/provider/Gemini project dashboards to set cost/read/write/rate limits; source configuration is not actual usage.

## 15. Ready / partial / blocked register

| Ready to build/test now (offline) | Partial / requires integration or policy | Blocked pending evidence/approval |
|---|---|---|
| Schema, observation identity, series comparability/period validation, fixed threshold tests; entity resolver; deterministic trend math on test fixtures; API contract tests; local reference ingestion tests | Profiles and skills; dashboards; stored current job retrieval; actions/role fit; company relationship/workforce aggregates; assistant orchestration; cache/read-cost observability; UI evidence/freshness integration | Operational demand forecast; Skill Half-Life claims; production market coverage assertions; live source collection/scheduler; AI task exposure; predictive workforce simulation; deployed rules/index/security certification; historical backfill absent licensed snapshot |

## Review and safety record

- **Primary deliverable:** `docs/TALENTSCOPE_AI_MASTER_DEVELOPMENT_BLUEPRINT.md`.
- **Supporting document reused:** `docs/AI_2A_ARCHITECTURE_AUDIT.md`; no repetitive audit set created.
- **Runtime/application files changed:** none. Existing working-tree edits were preserved.
- **Checks/tests:** no tests run (documentation-only); no runtime command, migration, model training, collector, browser login, or scheduler was run. `git diff --check` and Markdown whitespace checks are to be run for the new document.
- **External/production access:** none. No Firebase Admin/client initialization, Firebase Auth/Firestore, Gemini, JSearch, Adzuna, GitHub, Stack Exchange, Wikipedia, market provider, production database, or production audit record was contacted or inspected. No secrets, `.env`, or Firebase debug log contents were read.
