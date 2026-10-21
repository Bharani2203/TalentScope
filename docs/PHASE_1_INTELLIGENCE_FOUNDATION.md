# Phase 1 — Actual Intelligence System and Foundation Fixes

## Scope and evidence boundary

This map is based on the current assistant registry, answer request builder, planner/capability catalog, orchestrator handlers, and offline tests. The brief described the manual failures by symptom but did not include the literal submitted questions, so the exact manual strings cannot be replayed. Tests below use the current feature prompts or otherwise equivalent offline examples. No production Firebase/Firestore, Gemini, or provider request was made. Local source and fixture behavior do not verify deployment configuration or production records.

The selectable frontend feature sends the user’s full `message`, current `domain`, and selected feature `capability_id`, plus `portal_type`, `conversation_id`, `client_message_id`, filters, selected skills/roles/companies, target role, location, and time range as applicable. The API call is authenticated `POST /api/v1/intelligence/answer` with a Bearer token. The planner is responsible for routing; the answer client forwards the selected feature separately from the natural-language question.

## Current selectable feature map

“Available” is the capability catalog’s implementation label; runtime readiness can still reject a request for missing evidence. “Partial” is explicitly limited by the catalog. None of these statuses proves that production data is present.

| Domain / frontend feature | Internal ID → backend capability | Source/store and readiness | Implementation state and observed result |
|---|---|---|---|
| Skill — Skill Demand Trends | `trend_velocity_analysis` → same | Configured `skill_market_signals` observation store; real, platform-collected, comparable monthly series; at least 4 consecutive periods. | Available with strict data gate. Skill-domain interest series is now excluded with a specific readiness reason; verified demand remains eligible. Adoption may be shown only with its developer-activity label. |
| Skill — Historical Skill Signals | `historical_signal_retrieval` → same | Stored market observations (Firestore or configured SQLite); returns empirical periods as stored, without gap filling. | Available; actual local/production coverage remains environment-dependent. |
| Skill — Skill & Role Alignment | `skill_gap_role_fit` → same | Selected/self-reported user skills plus exact O*NET or ESCO occupation and taxonomy skill rows. | Partial heuristic crosswalk; not a measured fit score or qualification judgment. Missing/ambiguous occupation blocks the comparison. |
| Skill — Evidence & Sources | `evidence_provenance_retrieval` → same | Stored observations, fetch runs, raw archive/calculation evidence where present. | Available handler; only stored evidence is returned. No evidence is manufactured when artifacts are absent. |
| Skill — Skill Reference | `skill_technology_reference` → same | Local entity registry and configured taxonomy reference store; ESCO URI/version where matched. | Available. Python is resolved through the configured registry/reference path; local fixture coverage is testable, production DB selection remains deployment-dependent. |
| Skill — Action Recommendation | `action_recommendations` → same | Deterministic action service, O*NET role context, and available core evidence; user context is optional input. | Available handler, bounded by local reference and profile data. No course catalog, completion promise, or guaranteed outcome. |
| Market — Market Snapshot | `market_snapshot` → same | Latest matching persisted market observation with provider/fetch-run provenance. | Available; a snapshot is a provider-query sample, not total market size. Empty store returns insufficient data. |
| Market — Technology & Hiring Signals | `historical_signal_retrieval` → same | Persisted demand/adoption/interest series and their source metadata. | Available; signal type and source must be distinguished. GitHub is developer adoption, not hiring demand. |
| Market — Market Trend & Velocity | `trend_velocity_analysis` → same | Comparable, real platform-collected monthly observations; at least 4 consecutive periods. | Available with strict readiness gate. The measured signal is disclosed; adoption is not described as hiring. |
| Market — Evidence & Sources | `evidence_provenance_retrieval` → same | Observation, fetch-run, raw archive, and calculation records available in the configured store. | Available handler; missing stored provenance stays unavailable. |
| Job — Verified Job Postings | `job_posting_search` → same | Normalized stored postings in the Firestore `jobs` path; query/country filters; bounded recent result set. | Partial, stored-data-only; never performs a live search. Empty or unavailable storage is not a successful result. |
| Job — Role Skill Requirements | `occupation_software_skills` → same | Local O*NET software-skill reference rows. | Available; taxonomy baseline, not a current employer survey or guarantee. |
| Job — Career Mobility Pathways | `related_occupations` → same | Local O*NET related-occupation/work-activity crosswalk. | Available; occupational relatedness is not hiring volume or compensation equivalence. |
| Job — Skill & Role Alignment | `skill_gap_role_fit` → same | Selected/self-reported skills and exact target occupation’s O*NET/ESCO requirements. | Partial heuristic crosswalk; no proficiency verification or quantitative fit score. |
| Job — Role Preparation Actions | `action_recommendations` → same | Deterministic action service, O*NET context, selected skills/profile where available. | Available handler; no approved learning-provider/course catalog. |

The frontend currently advertises exactly these 6 Skill, 4 Market, and 5 Job features. `getDomainCapabilities` filters those cards against the authenticated backend catalog’s capability ID, supported domain, status, and handler. The backend domain matrix and catalog remain authoritative; a card is not proof of available evidence.

## Confirmed root causes and corrective changes

1. **Selected feature could disagree with execution.** `IntentPlannerService.create_plan` let a confidently classified natural-language intent replace a different explicitly selected capability. The frontend passed both fields correctly, but the planner treated the selected feature as a hint. It now executes the selected capability when classification matches, uses it when intent is ambiguous, and returns clarification when a clear question conflicts. Existing tests that encoded silent override were changed to assert this contract. The answer renderer continues to label executed capabilities from server response fields.
**Additional confirmed root cause — Action Recommendation prompt priority.** Its current prompt says “What should I learn next based on evidence for …”, while the classifier previously returned as soon as it saw “evidence.” Action intent is now checked before generic evidence when both patterns occur, so the selected default prompt routes to `action_recommendations`.
2. **Incidental standalone C/R could be resolved as an entity.** The entity scanner accepted any isolated `c` or `r` token in a full question. It now scans these short names only when used as a specifically requested entity (for example “trend for C?”) or explicitly qualified as a language/programming term. The genuine ambiguous “trend for C?” path still requests disambiguation; incidental “I heard C mentioned; … Python …” no longer makes C primary.
3. **Skill Demand Trends could fall back to interest.** Trend calculation ranked demand, adoption, and interest, and accepted any ready result. The Skill domain now omits interest trends from its eligible result set and returns an explicit readiness explanation if an interest-only series exists. GitHub adoption behavior remains intact and explicitly labels developer activity. Existing minimum period, origin, history-type, panel, and quality gates were not relaxed.
4. **Job conversation IDs were locally scoped to a static profile.** `AIAssistant.resolveCurrentUserId` trusted `userProfileState.uid` (a seeded/demo UID in `src/app/state.js`) and checked a legacy session key, while auth state uses `talentscope_session_v2`. Multiple authenticated users could therefore restore the same assistant-local active conversation ID. The assistant now derives its local conversation/session scope only from a well-formed Firebase session whose `user.uid` matches `userId`; absent, malformed, local-only, or mismatched sessions map to `anonymous`. The backend still authenticates every request and rejects cross-user, cross-domain, and cross-portal access.

The literal manual test prompts were not included in the brief. Reproduction uses the selected feature plus representative current prompts; no hard-coded response was added. Existing market/reference/occupation handlers were also traced: they are implemented, but generic frontend “request failed” symptoms cannot be reproduced from absent production configuration using offline source review alone. Their backend missing-data behavior is structured, and authenticated API errors are preserved as errors.

## Conversation, response, and data path

The answer route requires `get_current_user`; the verified UID is passed to `ExecutionOrchestratorService`. Conversation context is retrieved with user, domain, and portal constraints; a mismatch remains denied. Frontend conversation IDs are now keyed from the validated Firebase session identity, with existing domain separation retained. Stored-job execution uses `search_stored_jsearch_jobs` and the normalized `jobs` store; it does not invoke a provider. Test-injected job results are marked `data_origin=test` and limitations identify them as test data.

Structured responses retain facts, evidence, limitations, capability IDs, execution status, and readiness. The frontend renderer uses response status and the executed/planned capability supplied by the backend. Existing tests cover success and insufficient-data rendering, auth failures, and structured evidence; live-browser token minting was deliberately not run. Internal logging/correlation behavior outside the reproduced routing/ownership issues was not modified in this phase.

## Offline regression coverage

- Current 15-feature frontend contract is asserted in `tests/assistant-filters.test.mjs` (6/4/5 counts and exact IDs) and request construction is asserted in the core intelligence client tests.
- Planner tests cover matching selected capability, ambiguous fallback to selected capability, explicit conflict clarification, selected domain mismatch, explicit skill/reference examples, and the standalone C ambiguity edge cases.
- Trend fixtures cover interest rejection and preserve the existing labeled GitHub adoption case.
- Conversation tests cover continuity, domain isolation, and explicit cross-user rejection; the new assistant identity unit test checks valid/mismatched/local/malformed storage shapes.
- Python taxonomy behavior is covered by `test_reference_data_integration.py` and the extracted ESCO/reference tests; these use local fixtures/database only and do not establish which data store is configured in deployment.

## Still incomplete or dependent on genuine data

- Trend and historical answers need populated, provenance-valid observations in the runtime-selected store; focused trend calculation still needs 4 strictly consecutive completed comparable monthly periods.
- Market and evidence features may return insufficient data when the runtime store has no matching persisted observations or provenance.
- Job search only reads normalized stored jobs and remains partial. Production Firestore presence was not checked.
- Skill/role alignment is heuristic; profile skills are self-reported and target occupation resolution must be exact.
- Actions do not use a verified course catalogue or assure outcomes.
- No production availability, production authentication state, actual Firestore job records, or external provider behavior was verified.

## Authorized staging verification later

After the normal project owner approves a staging environment and uses non-production identities/data, verify sign-in for two distinct accounts; confirm assistant active conversation IDs are independently keyed by each authenticated UID and domain; confirm a same-user/same-domain follow-up reuses its conversation; confirm cross-user, cross-domain, and cross-portal access remains rejected. Exercise each of the 15 feature prompts against the staging API and record request ID/correlation ID, selected capability, planned/executed capability, status, readiness reason, source/provenance, and any safe server error. Confirm the configured taxonomy database and stored job path using authorized read-only inspection. Do not use production records for this check.
