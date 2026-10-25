from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime as RealDateTime, timezone

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.intelligence_v2.feature_policy import FEATURE_ANSWER_POLICIES
from app.intelligence_v2.orchestrator import V2Orchestrator
from app.intelligence_v2.contracts import V2StructuredFact
from app.intelligence_v2.skill_intelligence import SkillIntelligenceResult
from app.models.execution_orchestrator import CoreIntelligenceAnswerRequest
from app.services.gemini_b_guidance_service import GeminiBGuidanceService
from app.storage.reference_store import ReferenceDataStore


@pytest.fixture(autouse=True)
def reset_gemini_b_state():
    GeminiBGuidanceService._calls.clear()
    GeminiBGuidanceService._daily_count = 0
    GeminiBGuidanceService._day_key = ""
    GeminiBGuidanceService._user_calls.clear()
    GeminiBGuidanceService._cache.clear()
    GeminiBGuidanceService._inflight.clear()


def make_settings(**overrides):
    values = {
        "gemini_b_api_key": SecretStr("test-key"),
        "gemini_b_model": "test-model",
        "gemini_b_backup_model": None,
        "gemini_b_request_timeout_seconds": 1,
        "gemini_b_max_calls_per_minute": 10,
        "gemini_b_max_calls_per_day": 10,
        "gemini_b_max_calls_per_user_per_hour": 10,
        "gemini_b_max_input_chars": 3000,
        "gemini_b_max_output_tokens": 128,
    }
    values.update(overrides)
    return Settings.model_construct(**values)


def fake_response(text="Learn the core concepts, then practice with a small project.", status=200):
    payload = (
        {"candidates": [{"content": {"parts": [{"text": text}]}}]}
        if status == 200
        else {"error": {"code": status, "message": "Quota limit for model test-model"}}
    )
    return SimpleNamespace(
        status_code=status,
        json=lambda: payload,
    )


def test_gemini_a_and_b_settings_load_separately_from_environment_file(tmp_path):
    env_file = tmp_path / "fake-settings.env"
    env_file.write_text(
        "GEMINI_API_KEY=fake-gemini-a-key\n"
        "GEMINI_B_API_KEY=fake-gemini-b-key\n"
        "GEMINI_B_MODEL=offline-test-model\n"
        "GEMINI_B_BACKUP_MODEL=offline-backup-model\n",
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_file)

    assert settings.gemini_api_key.get_secret_value() == "fake-gemini-a-key"
    assert settings.gemini_b_api_key.get_secret_value() == "fake-gemini-b-key"
    assert settings.gemini_b_model == "offline-test-model"
    assert settings.gemini_b_backup_model == "offline-backup-model"


def test_b_limits_and_timeout_load_independently_and_are_bounded(tmp_path):
    env_file = tmp_path / "fake-limits.env"
    env_file.write_text(
        "GEMINI_MAX_CALLS_PER_MINUTE=3\n"
        "GEMINI_B_MAX_CALLS_PER_MINUTE=2\n"
        "GEMINI_B_MAX_CALLS_PER_DAY=7\n"
        "GEMINI_B_REQUEST_TIMEOUT_SECONDS=6\n",
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_file)

    assert settings.gemini_max_calls_per_minute == 3
    assert settings.gemini_b_max_calls_per_minute == 2
    assert settings.gemini_b_max_calls_per_day == 7
    assert settings.gemini_b_request_timeout_seconds == 6
    with pytest.raises(ValueError):
        Settings(_env_file=None, GEMINI_B_REQUEST_TIMEOUT_SECONDS=0)


def test_gemini_b_model_uses_existing_source_default_when_not_overridden():
    settings = Settings(_env_file=None)

    assert settings.gemini_b_model == "gemini-3.8-flash"


def test_feature_policy_covers_all_registered_canonical_features():
    from app.intelligence_v2.capability_registry import APPROVED_CAPABILITY_IDS, CAPABILITIES

    # The selectable registry has seven approved features. These three
    # engine/provider-only policies are also required by the answer pipeline.
    supplemental_policies = {
        "skill_demand_trends",
        "skill_reference_profile",
        "job_verified_postings",
    }
    assert set(CAPABILITIES) == APPROVED_CAPABILITY_IDS
    assert set(FEATURE_ANSWER_POLICIES) == APPROVED_CAPABILITY_IDS | supplemental_policies
    assert not FEATURE_ANSWER_POLICIES["job_verified_postings"].gemini_b_fallback
    assert FEATURE_ANSWER_POLICIES["job_verified_postings"].provider_data_required
    # These legacy engine IDs are not registered for static Gemini guidance.
    assert "skill_evidence_citations" not in FEATURE_ANSWER_POLICIES
    assert "market_evidence_citations" not in FEATURE_ANSWER_POLICIES
    assert "skill_role_alignment" not in FEATURE_ANSWER_POLICIES
    assert "job_profile_alignment" not in FEATURE_ANSWER_POLICIES


def test_gemini_b_missing_key_fails_closed_without_sending():
    sends = []
    service = GeminiBGuidanceService(make_settings(gemini_b_api_key=None), sender=lambda *a, **k: sends.append(1))
    assert service.generate(capability_id="skill_demand_trends") is None
    assert sends == []


def test_default_network_sender_is_disabled_in_pytest(monkeypatch):
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "offline-test")
    settings = make_settings()
    service = GeminiBGuidanceService(settings)
    assert service.generate(capability_id="skill_demand_trends") is None


def test_quota_exhaustion_fails_closed_without_sending():
    sends = []
    service = GeminiBGuidanceService(make_settings(gemini_b_max_calls_per_minute=0), sender=lambda *a, **k: sends.append(1))
    assert service.generate(capability_id="skill_demand_trends") is None
    assert sends == []


def test_rejected_quota_reservation_does_not_increment_any_counter():
    settings = make_settings(gemini_b_max_calls_per_minute=0)
    assert not GeminiBGuidanceService._reserve_budget("user-a", settings, 10.0)
    assert not GeminiBGuidanceService._calls
    assert GeminiBGuidanceService._daily_count == 0
    assert not GeminiBGuidanceService._user_calls


def test_b_usage_ledger_enforces_independent_limits_and_user_window():
    from app.services.llm_explanation_service import LLMExplanationService

    settings = make_settings(
        gemini_max_calls_per_minute=0,
        gemini_max_calls_per_day=0,
        gemini_max_calls_per_user_per_hour=0,
        gemini_b_max_calls_per_minute=4,
        gemini_b_max_calls_per_day=4,
        gemini_b_max_calls_per_user_per_hour=1,
    )
    a = LLMExplanationService(settings=settings)
    assert a._GLOBAL_MAX_CALLS_PER_MINUTE == 0
    assert a._GLOBAL_MAX_CALLS_PER_DAY == 0
    assert a._USER_MAX_REQUESTS_PER_WINDOW == 0

    assert GeminiBGuidanceService._reserve_budget("user-a", settings, 100.0)
    assert not GeminiBGuidanceService._reserve_budget("user-a", settings, 101.0)
    assert GeminiBGuidanceService._reserve_budget("user-b", settings, 102.0)


def test_b_daily_limit_is_independent_of_minute_limit():
    settings = make_settings(gemini_b_max_calls_per_minute=5, gemini_b_max_calls_per_day=1)
    assert GeminiBGuidanceService._reserve_budget("user-a", settings, 100.0)
    assert not GeminiBGuidanceService._reserve_budget("user-b", settings, 101.0)


def test_b_minute_limit_expires_at_sixty_seconds():
    settings = make_settings(gemini_b_max_calls_per_minute=1)
    assert GeminiBGuidanceService._reserve_budget("user-a", settings, 100.0)
    assert not GeminiBGuidanceService._reserve_budget("user-b", settings, 159.0)
    assert GeminiBGuidanceService._reserve_budget("user-b", settings, 160.0)


def test_b_hourly_user_limit_survives_reservations_and_utc_midnight(monkeypatch):
    import app.services.gemini_b_guidance_service as gemini_b_module

    class Clock:
        current = RealDateTime(2026, 10, 20, 23, 55, tzinfo=timezone.utc)

        @classmethod
        def now(cls, tz=None):
            return cls.current

    monkeypatch.setattr(gemini_b_module, "datetime", Clock)
    settings = make_settings(gemini_b_max_calls_per_user_per_hour=1)

    assert GeminiBGuidanceService._reserve_budget("user-a", settings, 10_000.0)
    Clock.current = RealDateTime(2026, 10, 21, 0, 5, tzinfo=timezone.utc)
    assert not GeminiBGuidanceService._reserve_budget("user-a", settings, 10_600.0)


def test_b_daily_counter_resets_at_utc_calendar_day_boundary(monkeypatch):
    import app.services.gemini_b_guidance_service as gemini_b_module

    class Clock:
        current = RealDateTime(2026, 10, 20, 23, 59, tzinfo=timezone.utc)

        @classmethod
        def now(cls, tz=None):
            return cls.current

    monkeypatch.setattr(gemini_b_module, "datetime", Clock)
    settings = make_settings(gemini_b_max_calls_per_day=1)

    assert GeminiBGuidanceService._reserve_budget("user-a", settings, 20_000.0)
    assert not GeminiBGuidanceService._reserve_budget("user-b", settings, 20_010.0)
    Clock.current = RealDateTime(2026, 10, 21, 0, 0, tzinfo=timezone.utc)
    assert GeminiBGuidanceService._reserve_budget("user-b", settings, 20_020.0)


def test_b_anonymous_identifiers_share_the_anonymous_hourly_bucket():
    settings = make_settings(gemini_b_max_calls_per_user_per_hour=1)
    assert GeminiBGuidanceService._reserve_budget(None, settings, 100.0)
    assert not GeminiBGuidanceService._reserve_budget("", settings, 101.0)


def test_b_quota_reservation_is_atomic_within_one_process():
    settings = make_settings(gemini_b_max_calls_per_minute=3, gemini_b_max_calls_per_day=50)
    with ThreadPoolExecutor(max_workers=12) as pool:
        reserved = list(pool.map(
            lambda index: GeminiBGuidanceService._reserve_budget(f"user-{index}", settings, 100.0),
            range(12),
        ))
    assert sum(reserved) == 3


def test_timeout_and_non_success_response_return_no_guidance():
    def timeout(*args, **kwargs):
        raise httpx.TimeoutException("test timeout")

    service = GeminiBGuidanceService(make_settings(), sender=timeout)
    assert service.generate(capability_id="skill_historical_signals") is None
    service = GeminiBGuidanceService(make_settings(), sender=lambda *a, **k: fake_response(status=429))
    assert service.generate(capability_id="skill_historical_signals") is None


def test_invalid_provider_payload_returns_no_guidance():
    response = SimpleNamespace(status_code=200, json=lambda: {"candidates": []})
    service = GeminiBGuidanceService(make_settings(), sender=lambda *a, **k: response)
    assert service.generate(capability_id="skill_historical_signals") is None


@pytest.mark.parametrize("text", [
    "Hiring demand increased by 20 percent.",
    "Source: https://example.test/fake-citation",
    "[Python jobs](https://example.test)",
])
def test_malformed_or_unsupported_claims_are_rejected(text):
    service = GeminiBGuidanceService(make_settings(), sender=lambda *a, **k: fake_response(text))
    assert service.generate(capability_id="skill_demand_trends") is None


def test_gemini_b_sends_only_static_policy_and_public_skill_label():
    sent = {}
    calls = []

    def sender(url, **kwargs):
        calls.append(url)
        sent.update(url=url, **kwargs)
        return fake_response()

    service = GeminiBGuidanceService(make_settings(), sender=sender)
    answer = service.generate(capability_id="skill_demand_trends", public_skill_name="Python")
    assert answer and "small project" in answer
    body = str(sent["json"])
    assert "Python" in body
    assert "user message" not in body.casefold()
    assert "employee profile" not in body.casefold()
    assert sent["timeout"] == 1
    assert sent["url"].endswith("/models/test-model:generateContent")
    assert "temperature" not in sent["json"]["generationConfig"]
    assert len(calls) == 1


def test_primary_model_success_does_not_call_backup():
    calls = []
    settings = make_settings(gemini_b_backup_model="backup-model")
    service = GeminiBGuidanceService(settings, sender=lambda url, **kwargs: (calls.append(url), fake_response())[1])

    assert service.generate(capability_id="skill_reference_profile", public_skill_name="Python")
    assert len(calls) == 1
    assert "/models/test-model:" in calls[0]


def test_primary_rate_limit_uses_one_configured_backup_attempt():
    calls = []

    def sender(url, **kwargs):
        calls.append(url)
        return fake_response(status=429) if len(calls) == 1 else fake_response()

    service = GeminiBGuidanceService(make_settings(gemini_b_backup_model="backup-model"), sender=sender)

    assert service.generate(capability_id="skill_reference_profile", public_skill_name="Python")
    assert len(calls) == 2
    assert "/models/test-model:" in calls[0]
    assert "/models/backup-model:" in calls[1]


def test_account_level_429_does_not_spend_quota_on_backup():
    calls = []
    account_quota_error = SimpleNamespace(
        status_code=429,
        json=lambda: {"error": {"code": 429, "message": "Project request quota exhausted"}},
    )

    def sender(url, **kwargs):
        calls.append(url)
        return account_quota_error

    service = GeminiBGuidanceService(make_settings(gemini_b_backup_model="backup-model"), sender=sender)

    assert service.generate(capability_id="skill_reference_profile", public_skill_name="Python") is None
    assert len(calls) == 1


def test_no_backup_configuration_makes_only_one_primary_attempt():
    calls = []
    service = GeminiBGuidanceService(
        make_settings(gemini_b_backup_model=None),
        sender=lambda url, **kwargs: (calls.append(url), fake_response(status=429))[1],
    )

    assert service.generate(capability_id="skill_reference_profile", public_skill_name="Python") is None
    assert len(calls) == 1


def test_invalid_success_response_does_not_trigger_backup():
    calls = []
    invalid = SimpleNamespace(status_code=200, json=lambda: {"candidates": []})
    service = GeminiBGuidanceService(
        make_settings(gemini_b_backup_model="backup-model"),
        sender=lambda url, **kwargs: (calls.append(url), invalid)[1],
    )

    assert service.generate(capability_id="skill_reference_profile", public_skill_name="Python") is None
    assert len(calls) == 1


def test_both_models_failing_stops_after_one_backup_attempt():
    calls = []

    def sender(url, **kwargs):
        calls.append(url)
        return fake_response(status=503)

    service = GeminiBGuidanceService(make_settings(gemini_b_backup_model="backup-model"), sender=sender)

    assert service.generate(capability_id="skill_reference_profile", public_skill_name="Python") is None
    assert len(calls) == 2


def test_backup_attempt_reserves_a_second_b_application_quota_unit():
    calls = []
    service = GeminiBGuidanceService(
        make_settings(gemini_b_backup_model="backup-model", gemini_b_max_calls_per_day=1),
        sender=lambda url, **kwargs: (calls.append(url), fake_response(status=429))[1],
    )

    assert service.generate(capability_id="skill_reference_profile", public_skill_name="Python") is None
    assert len(calls) == 1


@pytest.mark.usefixtures("injected_empty_firestore")
def test_successful_deterministic_result_does_not_call_gemini_b():
    class NoCallB:
        def generate(self, **kwargs):
            raise AssertionError("Gemini B must not run when deterministic results are useful")

    store = ReferenceDataStore(read_only=True)
    orchestrator = V2Orchestrator(store=store, conversation_store=object(), gemini_b_service=NoCallB())
    orchestrator.capability_registry.evaluate_readiness = lambda *a, **k: SimpleNamespace(
        is_executable=True, state="ready", reason="ready"
    )
    orchestrator.skill_engine.run_historical_signals = lambda *a, **k: SkillIntelligenceResult(
        capability_id="skill_historical_signals", target_skill="Python", headline="Stored history was retrieved.",
    facts=[V2StructuredFact(fact_id="fixture:history:1", fact_type="historical_observation",
                            metric_name="pushers", metric_value=12,
                            source="Test fixture", period="2025-Q1")],
    )
    response = orchestrator.execute_request(CoreIntelligenceAnswerRequest(
        message="explain Python history", domain="skill", capability_id="historical_signal_retrieval"
    ))
    assert response.execution_status == "completed"
    assert response.source_mode == "platform_data"


@pytest.mark.usefixtures("injected_empty_firestore")
def test_missing_data_uses_b_and_returns_guidance_without_evidence_or_visualization():
    class FakeB:
        def __init__(self):
            self.calls = []

        def generate(self, **kwargs):
            self.calls.append(kwargs)
            return "Learn the core concepts, then practice with a small project."

    store = ReferenceDataStore(read_only=True)
    b = FakeB()
    orchestrator = V2Orchestrator(store=store, conversation_store=object(), gemini_b_service=b)
    orchestrator.capability_registry.evaluate_readiness = lambda *a, **k: SimpleNamespace(
        is_executable=False, state="insufficient_data", reason="No comparable periods are available."
    )
    response = orchestrator.execute_request(CoreIntelligenceAnswerRequest(
        message="Python hiring observations are needed for my private profile", domain="skill",
        capability_id="trend_velocity_analysis", selected_skills=["PrivateProfileSkill"],
    ))
    assert len(b.calls) == 1
    assert b.calls[0]["capability_id"] == "skill_demand_trends"
    assert b.calls[0]["public_skill_name"] is None
    assert "private profile" not in str(b.calls[0]).casefold()
    assert response.source_mode == "ai_general_guidance"
    assert response.answer_origin == "gemini"
    assert response.evidence == []
    assert response.visualization is None
    assert response.status == "ready"
    assert response.reason_codes == ["AI_GENERAL_GUIDANCE_ONLY"]


def test_missing_b_never_calls_gemini_a(monkeypatch):
    from app.services.llm_explanation_service import LLMExplanationService

    def forbidden_a_call(*args, **kwargs):
        raise AssertionError("Gemini A must never be an implicit fallback")

    monkeypatch.setattr(LLMExplanationService, "generate_grounded_explanation", forbidden_a_call)
    service = GeminiBGuidanceService(make_settings(gemini_b_api_key=None), sender=lambda *a, **k: None)
    assert service.generate(capability_id="skill_historical_signals") is None


def test_primary_and_backup_failure_never_calls_gemini_a(monkeypatch):
    from app.services.llm_explanation_service import LLMExplanationService

    def forbidden_a_call(*args, **kwargs):
        raise AssertionError("Gemini A must never be a Gemini B fallback")

    monkeypatch.setattr(LLMExplanationService, "generate_grounded_explanation", forbidden_a_call)
    service = GeminiBGuidanceService(
        make_settings(gemini_b_backup_model="backup-model"),
        sender=lambda *args, **kwargs: fake_response(status=503),
    )
    assert service.generate(capability_id="skill_historical_signals") is None


@pytest.mark.usefixtures("injected_empty_firestore")
def test_provider_only_features_are_never_replaced_by_guidance():
    class NoCallB:
        def generate(self, **kwargs):
            raise AssertionError("Provider-only feature must not invoke Gemini B")

    store = ReferenceDataStore(read_only=True)
    orchestrator = V2Orchestrator(store=store, conversation_store=object(), gemini_b_service=NoCallB())
    response = orchestrator._maybe_apply_gemini_b(
        SimpleNamespace(status="insufficient_data", facts=[], evidence=[]),
        "job_verified_postings", None,
        CoreIntelligenceAnswerRequest(message="show postings", domain="job", capability_id="job_posting_search"),
        "anonymous", "individual", None,
    )
    assert response.status == "insufficient_data"

    for capability_id, request_capability in (
        ("skill_evidence_citations", "evidence_citation_retrieval"),
        ("market_evidence_citations", "evidence_citation_retrieval"),
    ):
        response = orchestrator._maybe_apply_gemini_b(
            SimpleNamespace(status="insufficient_data", facts=[], evidence=[]),
            capability_id, None,
            CoreIntelligenceAnswerRequest(message="show sources", domain="skill", capability_id=request_capability),
            "anonymous", "individual", None,
        )
        assert response.status == "insufficient_data"


@pytest.mark.usefixtures("injected_empty_firestore")
def test_gemini_b_failure_preserves_insufficient_data_response():
    class FailedB:
        def generate(self, **kwargs):
            return None

    store = ReferenceDataStore(read_only=True)
    orchestrator = V2Orchestrator(store=store, conversation_store=object(), gemini_b_service=FailedB())
    orchestrator.capability_registry.evaluate_readiness = lambda *a, **k: SimpleNamespace(
        is_executable=False, state="insufficient_data", reason="No comparable periods are available."
    )
    response = orchestrator.execute_request(CoreIntelligenceAnswerRequest(
        message="Python hiring trend", domain="skill", capability_id="trend_velocity_analysis",
    ))
    assert response.status == "insufficient_data"
    assert response.answer_origin != "gemini"
    assert response.source_mode != "ai_general_guidance"
    assert response.answer and "period" in response.answer.casefold()
    assert "no new measured market data" in response.answer.casefold()
    assert len(response.next_actions) == 2
