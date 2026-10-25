# Backend testing

## Safe defaults

Run backend tests from `backend\` with live-test opt-ins unset. The pytest
autouse network guard blocks outbound traffic and permits only the local
Firestore and Auth emulator endpoints (`127.0.0.1:8080` and
`127.0.0.1:9099`). The demo and provider-resilience suites use injected
in-memory Firestore and mocked providers; they do not require an emulator or
credentials.

The six-variable emulator configuration is only needed for tests explicitly
using the live emulator fixture:

| Variable | Local-test value |
|---|---|
| `TALENTSCOPE_FIREBASE_MODE` | `emulator` |
| `TALENTSCOPE_OFFLINE_TEST_MODE` | `1` |
| `ENVIRONMENT` | `local-test` |
| `FIREBASE_PROJECT_ID` | `demo-talentscope-local` |
| `FIRESTORE_EMULATOR_HOST` | `127.0.0.1:8080` |
| `FIREBASE_AUTH_EMULATOR_HOST` | `127.0.0.1:9099` |

Do not set `RUN_LIVE_FIRESTORE_TESTS`, `RUN_LIVE_LLM_TESTS`, or
`RUN_LIVE_GEMINI_TESTS` when running the mocked suite set. The demo route tests
inject a `MockFirestoreClient`; even when the six emulator-mode variables are
present, they must not be used to connect to a real Firestore or provider.

## Suite environment requirements

The command below runs the 17 related suites and the demo regression suite.
For this complete set, no emulator variables are required. Provider tests use
test doubles and need no provider credentials or provider environment
variables. In particular, keep `TALENTSCOPE_OFFLINE_TEST_MODE` unset while
running the provider-resilience tests: setting it disables the provider
availability paths those tests mock.

| Suite | Environment required |
|---|---|
| `test_assistant_phase_b_mocked.py` | None; mocked handlers and in-memory Firestore |
| `test_b1_answer_presentation_mocked.py` | None |
| `test_b2_question_classification_mocked.py` | None |
| `test_check_gemini_live.py` | None externally; tests replace provider sends with mocks |
| `test_collected_posting_skills_mocked.py` | None; mocked data |
| `test_firebase_admin.py` | None externally; emulator settings are set by individual tests |
| `test_gemini_b_guidance.py` | None; mock sender/settings |
| `test_gemini_provider_resilience_mocked.py` | None; mock transport; leave live opt-ins unset |
| `test_intelligence_v2.py` | None; injected in-memory Firestore |
| `test_intent_planner.py` | None |
| `test_market_collection.py` | None; mocked collection dependencies |
| `test_phase1_source_registry.py` | None; injected in-memory Firestore |
| `test_phase4b_data_recovery_and_routing.py` | None |
| `test_phase7_shared_intelligence.py` | None; injected in-memory Firestore |
| `test_public_company_job_boards.py` | None; mocked HTTP/provider responses |
| `test_read_efficiency.py` | None; injected in-memory Firestore |
| `test_v2_gemini_b_and_presentation.py` | None; mocked Firestore and Gemini B |
| `test_demo_questions_mocked.py` | TestClient, injected in-memory Firestore, mocked providers; no emulator connection. If the process is deliberately run in emulator mode, use all six local-test variables above. |

The demo suite includes a mixed-city set of 22 synthetic stored postings. It
checks Bangalore/Bengaluru alias matching, Chennai matching, a zero-match
Kolkata search, remote-only results, truthful scanned/matched/city counts,
the “Live search is off” disclosure, and that returned URLs are exactly the
stored source URLs. These route tests use only the in-memory Firestore client.

The `/plan` endpoint uses the canonical V2 capability for the five currently
aligned demo capabilities and produces a plain-language `understood` sentence.
If V2 planning raises, `/plan` logs only the exception class and returns the
legacy plan unchanged. The unsupported comparison question returns a
clarification without a selected capability.

To run every backend test file, with live integration opt-ins left unset:

```powershell
Set-Location backend
python -m pytest --timeout=60 -q tests
```

The focused 18-suite command used for the demo validation is:

```powershell
python -m pytest --timeout=60 -q `
  tests\test_assistant_phase_b_mocked.py `
  tests\test_b1_answer_presentation_mocked.py `
  tests\test_b2_question_classification_mocked.py `
  tests\test_check_gemini_live.py `
  tests\test_collected_posting_skills_mocked.py `
  tests\test_firebase_admin.py `
  tests\test_gemini_b_guidance.py `
  tests\test_gemini_provider_resilience_mocked.py `
  tests\test_intelligence_v2.py `
  tests\test_intent_planner.py `
  tests\test_market_collection.py `
  tests\test_phase1_source_registry.py `
  tests\test_phase4b_data_recovery_and_routing.py `
  tests\test_phase7_shared_intelligence.py `
  tests\test_public_company_job_boards.py `
  tests\test_read_efficiency.py `
  tests\test_v2_gemini_b_and_presentation.py `
  tests\test_demo_questions_mocked.py
```

The read-only occupation-answer integration check uses the checked-in SQLite
reference database and makes no provider, Gemini, or Firestore calls:

```powershell
python -m pytest --timeout=60 -q tests\test_reference_occupation_real_database.py
```

## Known baseline failures

The following 30 failures were present in the baseline comparison at
`e74038b`; they are not regressions from the demo-route changes. The groups
below summarize the failing assertions and observed result differences.

| Group | Count | Tests and observed mismatch |
|---|---:|---|
| A — Registry size | 1 | `test_all_15_capabilities_registered`: expects 15 selectable capabilities; the current selectable registry contains 7. |
| B — Readiness state | 2 | `test_market_trend_velocity_readiness_insufficient` and `test_skill_role_alignment_readiness_requires_profile`: expect `insufficient_data`, receive `disabled`. |
| C — Execution/readiness outcomes | 6 | `test_market_trend_missing_data_uses_only_labelled_gemini_b_guidance_and_safe_fallback` expects a Gemini B guidance call that does not occur; `test_ready_market_adoption_series_does_not_consume_gemini_b`, `test_ready_role_preparation_actions_bypasses_gemini_b`, `test_job_verified_postings_bypasses_gemini_b`, `test_career_mobility_pathways_bypasses_gemini_b`, and `test_market_trend_velocity_insufficient_data_invokes_gemini_b` expect ready results but receive errors. |
| D — Explicit capability support | 14 | `test_explicit_capability_override_supersedes_keywords` expects `ready`, receives `error`. The 13 failing cases of `test_all_fifteen_canonical_capabilities_execute_without_keyword_override` expect executable capabilities but receive `unsupported`: `skill_role_alignment`, `skill_evidence_citations`, `skill_reference_profile`, `skill_action_recommendations`, `market_intelligence_snapshot`, `market_tech_signals`, `market_trend_velocity`, `market_evidence_citations`, `job_verified_postings`, `job_role_requirements`, `job_mobility_pathways`, `job_profile_alignment`, and `job_preparation_actions`. |
| E — Ineligible Gemini B policy | 4 | `test_ineligible_features_never_invoke_gemini_b` cases for `skill_evidence_citations`, `market_evidence_citations`, `skill_role_alignment`, and `job_profile_alignment` fail their expected policy assertion. |
| F — Alias and presentation contracts | 3 | `test_canonical_capability_alias_resolution` expects a different canonical ID set; `test_presentation_answer_types_and_comparison` expects `comparison` but receives `other`; `test_role_preparation_actions_and_job_preparation_actions_parity` expects `job_preparation_actions` but receives `role_preparation_actions`. |
| **Total** | **30** | **395 passed, 30 failed, 0 errors, 0 skipped in the final 18-suite run (425 total tests).** |

After plan alignment, mixed-city search filtering, count reporting, remote
filtering, and V2 planner exception fallback, the final 18-suite run had the
same 30 failure identities as the previous run: zero new failures and zero
cleared failures.

## Known failures outside the original 30

These counts are from the requested two-suite run
(`test_role_preparation_actions.py` and `test_esco_real_database_answer.py`)
with the project virtual environment and emulator-only configuration. At
`e74038b`, the result was **34 failed, 19 passed**. In the current tree, it was
**20 failed, 33 passed**. Every current failure identity also failed at the
baseline; none of these current failures is introduced by the occupation
answer changes. Fourteen baseline failures no longer reproduce.

| Group | Count | Failing tests | Cause and proposed fix |
|---|---:|---|---|
| A — Legacy role capability contracts | 3 | `test_capability_registration_and_aliases`; `test_feature_policy_configuration`; `test_explicit_capability_routing` | These tests expect the older role-preparation registry/policy and canonical routing contract. Proposed fix: reconcile the legacy aliases and policy lookup with the active V2 registry, retaining the explicit route contract. |
| B — ESCO occupation relation resolution and response contract | 5 | `test_selected_skill_reference_returns_data_analyst_esco_relations`; `test_real_esco_occupation_question_uses_imported_relationship_rows`; `test_essential_esco_question_filters_optional_relationships`; `test_http_answer_returns_imported_esco_occupation_relationships`; `test_http_selected_skill_reference_renders_occupation_relations_in_response_contract` | **Suspected cause (assertion output not reviewed):** ESCO occupation queries may resolve through the wrong planner/source path or return facts/status/relationship values that differ from this legacy contract. Proposed fix: route explicit ESCO occupation requests through ESCO relation rows and serialize relation type, source, and completion status consistently. |
| C — ESCO role alignment and action recommendations | 4 | `test_http_selected_role_alignment_compares_request_skills_to_esco_data_analyst`; `test_http_selected_action_recommendations_use_real_esco_when_onet_has_no_exact_match`; `test_esco_action_recommendations_compare_supplied_skills_against_real_relationships`; `test_esco_action_recommendations_do_not_turn_unresolved_skills_into_a_personal_gap` | **Suspected cause (assertion output not reviewed):** role-fit/action expectations may differ from the current capability execution and ESCO gap-resolution path. Proposed fix: align role-fit and action handlers to the exact ESCO occupation relations, preserving the unresolved-skill guard. |
| D — Historical and market capability routing | 5 | `test_http_selected_historical_feature_reads_local_github_series`; `test_http_selected_demand_trends_reports_no_local_market_history`; `test_http_market_snapshot_and_hiring_signals_do_not_fall_back_to_reference_data[Give me a market snapshot for Python in India.]`; `test_http_market_snapshot_and_hiring_signals_do_not_fall_back_to_reference_data[What hiring signals are available for Python in India?]`; `test_http_market_trend_question_keeps_hiring_source_and_readiness` | **Suspected cause (assertion output not reviewed):** these tests may expect selected historical/market capability IDs and intent labels that the current planner does not emit consistently. Proposed fix: make explicit capability selection authoritative and return a single consistent planned capability/intent contract for each request. |
| E — Local-only access, status propagation, and empty-database assumptions | 3 | `test_current_python_demand_does_not_fall_back_to_esco_or_onet`; `test_http_job_posting_search_uses_country_from_question_and_local_store_only`; `test_http_demand_question_does_not_use_esco_as_live_hiring_evidence` | The first test reaches a Firestore guard despite its SQLite-only fixture; the posting test receives `ready` where it expects `insufficient_data`; the demand test assumes an empty observations table, but the database contains 167,159 rows. Proposed fixes: keep collected-posting aggregation local under the SQLite-only configuration, propagate insufficient-data status when there are no postings, and give empty-database tests a dedicated empty DB fixture. |

For these three failures, the observed mismatches were:

- `test_current_python_demand_does_not_fall_back_to_esco_or_onet`: the
  `forbid_firestore` test guard raises while collected-posting aggregation
  calls `get_firestore_client()` despite the fixture's
  `skill_intelligence_read_backend="sqlite"` setting. Proposed fix: ensure
  the collected-posting path respects local-only configuration or inject an
  explicit local test client.
- `test_http_job_posting_search_uses_country_from_question_and_local_store_only`:
  expects `payload["status"] == "insufficient_data"`, receives `"ready"`;
  the fixture configures `skill_intelligence_read_backend="sqlite"`, so this
  mismatch is a response-status contract discrepancy, not evidence of a
  Firestore job-store read. Proposed fix: propagate insufficient-data status
  when the stored-posting result is empty.
- `test_http_demand_question_does_not_use_esco_as_live_hiring_evidence`:
  expects `market_store.get_observations() == []`, but the local database
  returns 167,159 observations; this is a stale empty-database assumption.

An earlier standalone role-preparation invocation without the required
emulator environment also produced four setup errors; they did not occur in
the comparable two-suite runs above and are not part of the 20 failures.

## Mixed-city search behavior

The V2 stored-posting search now shares city and remote filtering with the
Phase B stored-search path. Bangalore and Bengaluru are explicitly treated as
aliases. A requested city is applied before returning results; no results from
other cities are used as a fallback. The response includes the scanned count,
matched count, requested city, and “Live search is off.” An empty city result
is returned as insufficient data.
