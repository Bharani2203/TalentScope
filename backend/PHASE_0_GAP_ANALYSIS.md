# Backend Master Plan Gap Analysis — Phase 0

Repository comparison uses the approved constraints supplied in the development request. The master-plan source file was not present in the checkout. A read-only inventory of the configured Firestore project returned the top-level `users` collection; repository source also defines `jobs`. No existing `fetch_runs`, `skill_market_signals`, or `skill_market_history` collection was found in the live inventory.

| Area | Existing | Missing | Incorrect / risk | Reusable | Needs migration | Owner | Phase |
|---|---|---|---|---|---|---|---|
| Firestore collections | Live project currently has `users`; source also defines `jobs` for JSearch job documents. | No live `fetch_runs`, `skill_market_signals`, or `skill_market_history` collection was found. | SQLite stores observations, aggregate collection runs, and calculation cache despite the approved MVP prohibition. | `get_firestore_client()` and established service-layer Firestore access. | Move observations and cache only after replacement validation; preserve SQLite data and functionality until then. | Backend data | Phase 0 / later migration |
| Market routes and API | `GET /api/v1/market/jobs`, admin `POST /api/v1/market/collect`; skill intelligence endpoints consumed by existing frontend. | No new endpoint is needed for observability or registry. | Collection response uses legacy aggregate status terms; keep this public contract stable in this phase. | Existing authenticated routes and response models. | No frontend contract migration in Phase 1.5. | Backend API | Phase 1 |
| Collectors | JSearch and Adzuna normalize job postings and derive demand observations; failures are isolated in the loop. | Per-provider Firestore run records and fetched/processed/rejected counts. GitHub/Stack Exchange/HN collectors and historical backfill are absent by scope. | SQLite collection-run table is not the approved final architecture. | Existing providers, normalization adapter, stable observation IDs, and SQLite insert-ignore retry safety. | Historical run/observation/cache migration is later work; do not remove SQLite now. | Backend collection | Phase 1 |
| Intelligence service | One service computes trends from existing SQLite observations; cached responses; existing UI contract. | Nothing in Phase 1.5 requires another engine or route. | Storage backend remains transitional. | `skill_intelligence_service.py`, `trend.py`, current response schema. | Migrate storage only after an approved replacement is validated. | Backend analytics | Existing / later migration |
| Skill extraction and profile model | `extract_skills()` scans aliases with case-insensitive word boundaries; onboarding and Individual My Skills store names. | Canonical IDs, source-specific mappings, explicit ambiguity handling, and a single registry. | Short aliases (`Go`, `R`, `C`, `Spring`) risk false matches; profile values do not carry IDs. | Existing extractor, category lookup, and normalization call sites. | Existing stored skill names can be resolved through registry aliases; persist canonical IDs only when a later data-contract migration is approved. | Backend skills | Phase 1.5 |
| Frontend contract | Home and Individual My Skills consume existing intelligence API; frontend does not trigger collection. | No UI change requested or needed. | None identified within this phase. | Existing API response and fetch behavior. | None in Phase 1.5. | Frontend / API | Existing |

## Firestore inventory from code

- Live inventory: `users` only.
- Source-defined: `users/{uid}` stores profile, onboarding, selected skills, and skill levels; `jobs/{job_id}` stores JSearch job records when present.
- `fetch_runs/{run_id}`: introduced in Phase 1 for one provider execution per document; it was absent from the pre-change live inventory.
- `skill_market_signals` and `skill_market_history` were absent from both source references and the pre-change live inventory; they were not created in this phase.

## Phase boundary

Phase 1 adds Firestore observability for current providers. Phase 1.5 centralizes aliases, canonical IDs, topic/tag mappings, word-boundary extraction, and ambiguous matching. Phase 2+ work, new providers, historical backfill, forecasting changes, and frontend changes remain out of scope.
