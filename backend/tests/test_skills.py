from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.api import dependencies
from app.api.dependencies import get_current_user
from app.analytics.trend import calculate_skill_trends
from app.core.config import Settings
from app.main import app
from app.models.auth import AuthenticatedUser
from app.models.skill_intelligence import (
    MarketObservation,
    SkillIntelligenceResponse,
    UserSkillsResponse,
)
from app.services import market_collection_service, onboarding_service, skill_intelligence_service
from app.storage.market_store import MarketDataStore


class FakeObservationReader:
    def __init__(self, database):
        self.database = database

    def get_observations(self, *, cutoff, location=None, **kwargs):
        rows = [item for item in getattr(self.database, "observations", []) if item.observed_at >= cutoff]
        if location:
            rows = [item for item in rows if (item.location or "").casefold() == location.casefold()]
        return rows

    def has_observations(self):
        return bool(getattr(self.database, "observations", []))


def test_profile_skill_aliases_resolve_to_one_canonical_display_name():
    entries = skill_intelligence_service._skill_entries({
        "skills": {
            "selected_skills": ["python3", "Python", "nodejs"],
            "skill_levels": {"python3": "Comfortable", "nodejs": "Beginner"},
        }
    })
    assert [entry.name for entry in entries] == ["Python", "Node.js"]
    assert [entry.level.value for entry in entries] == ["Comfortable", "Beginner"]


@pytest.fixture(autouse=True)
def clear_dependency_overrides(monkeypatch, tmp_path):
    app.dependency_overrides.clear()
    settings = Settings(
        _env_file=None,
        skill_intelligence_db_path=str(tmp_path / "market.sqlite3"),
        skill_intelligence_read_backend="sqlite",
    )
    monkeypatch.setattr(
        skill_intelligence_service,
        "get_settings",
        lambda: settings,
    )
    monkeypatch.setattr(market_collection_service, "get_settings", lambda: settings)
    yield
    app.dependency_overrides.clear()


class Snapshot:
    def __init__(self, value):
        self.value = deepcopy(value)
        self.exists = value is not None

    def to_dict(self):
        return deepcopy(self.value)


class Document:
    def __init__(self, database, collection, document_id):
        self.database = database
        self.path = f"{collection}/{document_id}"

    def get(self):
        if self.database.fail_reads:
            raise RuntimeError("mock Firestore failure")
        return Snapshot(self.database.documents.get(self.path))

    def update(self, updates):
        if self.database.fail_writes:
            raise RuntimeError("mock Firestore failure")
        current = self.database.documents[self.path]
        for path, value in updates.items():
            parts = path.split(".")
            target = current
            for part in parts[:-1]:
                target = target.setdefault(part, {})
            target[parts[-1]] = deepcopy(value)

    def set(self, value, merge=False):
        current = self.database.documents.get(self.path, {}) if merge else {}
        self.database.documents[self.path] = {**current, **deepcopy(value)}


class Collection:
    def __init__(self, database, name):
        self.database = database
        self.name = name

    def document(self, document_id):
        return Document(self.database, self.name, document_id)


class FakeFirestore:
    def __init__(self, documents=None, *, fail_reads=False, fail_writes=False):
        self.documents = deepcopy(documents or {})
        self.fail_reads = fail_reads
        self.fail_writes = fail_writes

    def collection(self, name):
        return Collection(self, name)


def individual(uid="user-a"):
    return AuthenticatedUser(
        uid=uid,
        email=f"{uid}@example.com",
        email_verified=True,
        display_name=uid,
    )


def profile_doc(uid, *, skills=None, levels=None, city="Bangalore", country="India"):
    return {
        "uid": uid,
        "user_type": "individual",
        "updated_at": datetime(2026, 9, 1, tzinfo=timezone.utc),
        "profile": {
            "basic_profile": {"city": city, "country": country},
            "skills": {
                "selected_skills": skills if skills is not None else [],
                "skill_levels": levels if levels is not None else {},
            },
        },
    }


def configure_database(monkeypatch, database):
    monkeypatch.setattr(onboarding_service, "get_firestore_client", lambda: database)
    monkeypatch.setattr(skill_intelligence_service, "get_firestore_client", lambda: database)
    database.observations = []
    monkeypatch.setattr(skill_intelligence_service, "FirestoreObservationStore", lambda: FakeObservationReader(database))
    monkeypatch.setattr(skill_intelligence_service, "FirestoreFetchRunStore", lambda: type("FetchRuns", (), {"collection_summary": lambda self: {"last_collection": None}})())
    monkeypatch.setattr(
        skill_intelligence_service.firestore,
        "SERVER_TIMESTAMP",
        datetime(2026, 10, 1, tzinfo=timezone.utc),
    )


def authenticate_as(uid="user-a"):
    app.dependency_overrides[get_current_user] = lambda: individual(uid)


def test_my_skills_requires_authentication():
    with TestClient(app) as client:
        response = client.get("/api/v1/skills/my")

    assert response.status_code == 401


def test_my_skills_rejects_invalid_firebase_token(monkeypatch):
    monkeypatch.setattr(dependencies, "get_firebase_app", lambda: object())
    monkeypatch.setattr(
        dependencies.auth,
        "verify_id_token",
        Mock(side_effect=ValueError("invalid token")),
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/skills/my",
            headers={"Authorization": "Bearer invalid-token"},
        )

    assert response.status_code == 401


def test_my_skills_returns_only_the_authenticated_users_profile(monkeypatch):
    database = FakeFirestore({
        "users/user-a": profile_doc(
            "user-a",
            skills=["Python", "Machine Learning"],
            levels={"Python": "Advanced", "Machine Learning": "Comfortable"},
        ),
        "users/user-b": profile_doc("user-b", skills=["Java", "Spring Boot"]),
    })
    configure_database(monkeypatch, database)
    authenticate_as("user-a")

    with TestClient(app) as client:
        response = client.get("/api/v1/skills/my?uid=user-b")

    assert response.status_code == 200
    assert response.json() == {
        "skills": [
            {"name": "Python", "level": "Advanced", "category": None},
            {"name": "Machine Learning", "level": "Comfortable", "category": None},
        ],
        "profile_updated_at": "2026-09-01T00:00:00Z",
    }


def test_my_skills_returns_empty_list_for_profile_without_selected_skills(monkeypatch):
    database = FakeFirestore({"users/user-a": profile_doc("user-a")})
    configure_database(monkeypatch, database)
    authenticate_as()

    with TestClient(app) as client:
        response = client.get("/api/v1/skills/my")

    assert response.status_code == 200
    assert response.json()["skills"] == []


def test_skill_levels_are_mapped_from_profile(monkeypatch):
    database = FakeFirestore({
        "users/user-a": profile_doc(
            "user-a",
            skills=["Python", "SQL", "Unknown Level"],
            levels={"Python": "Expert", "SQL": "Beginner", "Unknown Level": "Master"},
        )
    })
    configure_database(monkeypatch, database)
    authenticate_as()

    with TestClient(app) as client:
        response = client.get("/api/v1/skills/my")

    assert response.status_code == 200
    assert [item["level"] for item in response.json()["skills"]] == [
        "Expert",
        "Beginner",
        None,
    ]


def test_skill_update_changes_canonical_profile_and_preserves_other_fields(monkeypatch):
    database = FakeFirestore({
        "users/user-a": {
            **profile_doc("user-a", skills=["Python"], levels={"Python": "Advanced"}),
        }
    })
    database.documents["users/user-a"]["profile"]["interests"] = ["Fintech"]
    configure_database(monkeypatch, database)
    authenticate_as()

    with TestClient(app) as client:
        response = client.put(
            "/api/v1/skills/my",
            json={"skills": [
                {"name": "Python"},
                {"name": "SQL", "level": "Comfortable"},
            ]},
        )

    stored = database.documents["users/user-a"]
    assert response.status_code == 200
    assert stored["profile"]["skills"]["selected_skills"] == ["Python", "SQL"]
    assert stored["profile"]["skills"]["skill_levels"] == {
        "Python": "Advanced",
        "SQL": "Comfortable",
    }
    assert stored["profile"]["interests"] == ["Fintech"]
    assert response.json()["skills"][1]["level"] == "Comfortable"


def test_skill_update_can_clear_skills(monkeypatch):
    database = FakeFirestore({
        "users/user-a": profile_doc("user-a", skills=["Python"], levels={"Python": "Advanced"})
    })
    configure_database(monkeypatch, database)
    authenticate_as()

    with TestClient(app) as client:
        response = client.put("/api/v1/skills/my", json={"skills": []})

    assert response.status_code == 200
    assert response.json()["skills"] == []
    assert database.documents["users/user-a"]["profile"]["skills"]["skill_levels"] == {}


def test_saved_skill_changes_are_used_by_the_next_intelligence_request(monkeypatch):
    database = FakeFirestore({
        "users/user-a": profile_doc("user-a", skills=["Python"]),
        "users/user-b": profile_doc("user-b", skills=["Java", "Spring Boot"]),
    })
    configure_database(monkeypatch, database)
    authenticate_as("user-a")

    with TestClient(app) as client:
        saved = client.put(
            "/api/v1/skills/my",
            json={"skills": [{"name": "Python"}, {"name": "SQL"}]},
        )
        intelligence = client.get("/api/v1/skills/intelligence")

    assert saved.status_code == 200
    assert intelligence.status_code == 200
    assert intelligence.json()["profile_context"]["selected_skills"] == ["Python", "SQL"]
    assert intelligence.json()["data_status"] == "pending_source_data"
    assert intelligence.json()["data_state"] == "building"
    assert intelligence.json()["calculation"]["signal_type"] == "demand"
    assert intelligence.json()["calculation"]["observation_count"] == 0
    assert "SQL" in intelligence.json()["profile_context"]["selected_skills"]
    assert "Java" not in intelligence.text
    assert "Spring Boot" not in intelligence.text


def test_firestore_read_failure_is_reported(monkeypatch):
    database = FakeFirestore(fail_reads=True)
    configure_database(monkeypatch, database)
    authenticate_as()

    with TestClient(app) as client:
        response = client.get("/api/v1/skills/my")

    assert response.status_code == 503
    assert "mock Firestore" not in response.text


def test_intelligence_reports_firestore_failure(monkeypatch):
    configure_database(monkeypatch, FakeFirestore(fail_reads=True))
    authenticate_as()

    with TestClient(app) as client:
        response = client.get("/api/v1/skills/intelligence")

    assert response.status_code == 503
    assert "mock Firestore" not in response.text


def test_intelligence_uses_profile_skills_location_and_default_range(monkeypatch):
    database = FakeFirestore({
        "users/user-a": profile_doc("user-a", skills=["Python", "SQL"])
    })
    configure_database(monkeypatch, database)
    authenticate_as()

    with TestClient(app) as client:
        response = client.get("/api/v1/skills/intelligence")

    body = response.json()
    assert response.status_code == 200
    assert body["profile_context"] == {
        "location": "Bangalore",
        "selected_skills": ["Python", "SQL"],
    }
    assert body["filters"] == {"location": "Bangalore", "range": "6m", "skill": None}
    assert body["data_status"] == "pending_source_data"


def test_intelligence_accepts_contract_three_month_window(monkeypatch):
    database = FakeFirestore({
        "users/user-a": profile_doc("user-a", skills=["Python", "SQL"])
    })
    configure_database(monkeypatch, database)
    authenticate_as()

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/skills/intelligence",
            params={"location": "Chennai", "range": "3m", "skill": "SQL"},
        )

    assert response.status_code == 200
    assert response.json()["filters"] == {
        "location": "Chennai",
        "range": "3m",
        "skill": "SQL",
    }


@pytest.mark.parametrize("unsupported", ["1y", "12m", "365d", "90d", "1Y", "bogus"])
def test_intelligence_rejects_unsupported_historical_windows(unsupported):
    authenticate_as()
    with TestClient(app) as client:
        response = client.get("/api/v1/skills/intelligence", params={"range": unsupported})
    assert response.status_code == 422
    assert response.json()["error_code"] == "invalid_filter"


@pytest.mark.parametrize("window", ["7d", "30d", "3m", "6m"])
def test_intelligence_accepts_frozen_fixed_windows(monkeypatch, window):
    database = FakeFirestore({"users/user-a": profile_doc("user-a", skills=["Python"])})
    configure_database(monkeypatch, database)
    authenticate_as()
    with TestClient(app) as client:
        response = client.get("/api/v1/skills/intelligence", params={"range": window})
    assert response.status_code == 200
    assert response.json()["filters"]["range"] == window


@pytest.mark.parametrize("days", [7, 184])
def test_custom_window_inclusive_bounds_are_accepted(monkeypatch, days):
    database = FakeFirestore({"users/user-a": profile_doc("user-a", skills=["Python"])})
    configure_database(monkeypatch, database)
    authenticate_as()
    with TestClient(app) as client:
        response = client.get("/api/v1/skills/intelligence", params={"range": "custom", "days": days})
    assert response.status_code == 200
    assert response.json()["filters"]["range"] == "custom"
    assert response.json()["calculation"]["period_days"] == days


@pytest.mark.parametrize("days", [6, 185])
def test_custom_window_outside_bounds_is_rejected(days):
    authenticate_as()
    with TestClient(app) as client:
        response = client.get("/api/v1/skills/intelligence", params={"range": "custom", "days": days})
    assert response.status_code == 422
    assert response.json()["error_code"] == "invalid_filter"


def test_intelligence_reports_pending_market_source_without_fabricating_trends(monkeypatch):
    database = FakeFirestore({
        "users/user-a": profile_doc("user-a", skills=["Python"])
    })
    configure_database(monkeypatch, database)
    authenticate_as()

    with TestClient(app) as client:
        response = client.get("/api/v1/skills/intelligence")

    assert response.status_code == 200
    body = response.json()
    assert body["data_status"] == "pending_source_data"
    assert body["top_skills"] == []
    assert body["skill_trends"] == []
    assert body["market_top_skills"] == []
    assert body["personal_top_skills"] == []
    assert body["observations_count"] == 0
    assert body["historical_periods_count"] == 0


def test_intelligence_reports_insufficient_history_when_provider_is_configured(monkeypatch, tmp_path):
    database = FakeFirestore({
        "users/user-a": profile_doc("user-a", skills=["Python"])
    })
    configure_database(monkeypatch, database)
    settings = Settings(
        _env_file=None,
        jsearch_api_key="configured-for-test",
        skill_intelligence_db_path=str(tmp_path / "market.sqlite3"),
    )
    monkeypatch.setattr(skill_intelligence_service, "get_settings", lambda: settings)
    authenticate_as()

    with TestClient(app) as client:
        response = client.get("/api/v1/skills/intelligence")

    assert response.status_code == 200
    assert response.json()["data_status"] == "insufficient_data"


def test_intelligence_reports_failed_collection_without_fabricating_data(monkeypatch, tmp_path):
    database = FakeFirestore({
        "users/user-a": profile_doc("user-a", skills=["Python"])
    })
    configure_database(monkeypatch, database)
    failed_run_summary = {"last_collection": {"status": "failed", "providers": {}}}
    monkeypatch.setattr(
        skill_intelligence_service,
        "FirestoreFetchRunStore",
        lambda: type("FetchRuns", (), {"collection_summary": lambda self: failed_run_summary})(),
    )
    authenticate_as()

    with TestClient(app) as client:
        response = client.get("/api/v1/skills/intelligence")

    assert response.status_code == 200
    assert response.json()["data_status"] == "error"
    assert response.json()["market_top_skills"] == []


def test_intelligence_returns_empty_profile_skills_without_fabrication(monkeypatch):
    database = FakeFirestore({
        "users/user-a": profile_doc("user-a")
    })
    configure_database(monkeypatch, database)
    authenticate_as()

    with TestClient(app) as client:
        response = client.get("/api/v1/skills/intelligence")

    body = response.json()
    assert response.status_code == 200
    assert body["profile_context"]["selected_skills"] == []
    assert body["skill_trends"] == []


def _store_city_history(path, location="Chennai"):
    store = MarketDataStore(path)
    observations = []
    for period, (python_count, sql_count, react_count) in zip(
        _recent_completed_periods(),
        [(20, 50, 30), (40, 40, 20), (60, 30, 10), (80, 15, 5)],
    ):
        for index in range(python_count):
            observations.append(MarketObservation(
                id=f"{location}:{period}:python:{index}",
                source="jsearch",
                skill="Python",
                signal_type="demand",
                history_type="platform_collected",
                observed_at=datetime.fromisoformat(f"{period}-15T12:00:00+00:00"),
                period=period,
                location=location,
                scope="city",
                posting_id=f"{period}:python:{index}",
                value=1,
                data_origin="demo",
            ))
        for index in range(sql_count):
            observations.append(MarketObservation(
                id=f"{location}:{period}:sql:{index}",
                source="jsearch",
                skill="SQL",
                signal_type="demand",
                history_type="platform_collected",
                observed_at=datetime.fromisoformat(f"{period}-15T12:00:00+00:00"),
                period=period,
                location=location,
                scope="city",
                posting_id=f"{period}:sql:{index}",
                value=1,
                data_origin="demo",
            ))
        for index in range(react_count):
            observations.append(MarketObservation(
                id=f"{location}:{period}:react:{index}",
                source="jsearch",
                skill="React",
                signal_type="demand",
                history_type="platform_collected",
                observed_at=datetime.fromisoformat(f"{period}-15T12:00:00+00:00"),
                period=period,
                location=location,
                scope="city",
                posting_id=f"{period}:react:{index}",
                value=1,
                data_origin="demo",
            ))
    database = skill_intelligence_service.get_firestore_client()
    database.observations.extend(observations)
    class TestObservationSink:
        def insert_observations(self, rows):
            database.observations.extend(rows)
    return TestObservationSink()


def _recent_completed_periods():
    now = datetime.now(timezone.utc)
    current_month_index = now.year * 12 + now.month - 1
    periods = []
    for offset in range(4, 0, -1):
        year, month_index = divmod(current_month_index - offset, 12)
        periods.append(f"{year:04d}-{month_index + 1:02d}")
    return periods


def test_demo_observations_are_excluded_from_market_evidence_and_proficiency_remains(monkeypatch, tmp_path):
    database = FakeFirestore({
        "users/user-a": profile_doc(
            "user-a",
            skills=["Python", "SQL"],
            levels={"Python": "Comfortable", "SQL": "Advanced"},
            city="Chennai",
        ),
        "users/user-b": profile_doc(
            "user-b",
            skills=["Java"],
            levels={"Java": "Beginner"},
            city="Chennai",
        ),
    })
    configure_database(monkeypatch, database)
    _store_city_history(tmp_path / "market.sqlite3")
    authenticate_as("user-a")

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/skills/intelligence",
            params={"location": "Chennai", "range": "6m", "skill": "Python"},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["data_status"] == "insufficient_data"
    assert body["data_origin"] == "demo"
    assert body["data_state"] == "insufficient_data"
    assert body["calculation"]["observation_count"] == 0
    assert body["provenance"]["observation_count"] == 0
    assert body["provenance"]["sources"] == []
    assert body["profile_context"]["selected_skills"] == ["Python", "SQL"]
    assert body["personal_top_skills"] == []
    assert body["market_top_skills"] == []
    assert body["current_demand"] == []
    assert body["selected_skill"]["proficiency"] == "Comfortable"
    assert body["selected_skill"]["trend"] == "Insufficient Data"
    assert body["selected_skill"]["series"] == []
    assert body["observations_count"] == 400
    assert body["historical_periods_count"] == 4


def test_global_filter_does_not_treat_demo_observations_as_market_evidence(monkeypatch, tmp_path):
    database = FakeFirestore({
        "users/user-a": profile_doc(
            "user-a",
            skills=["Python"],
            city="Chennai",
        )
    })
    configure_database(monkeypatch, database)
    path = tmp_path / "market.sqlite3"
    _store_city_history(path, location="Chennai")
    _store_city_history(path, location="Pune")
    authenticate_as()

    with TestClient(app) as client:
        response = client.get("/api/v1/skills/intelligence", params={"location": "Global"})

    body = response.json()
    assert response.status_code == 200
    assert body["filters"]["location"] == "Global"
    assert body["data_origin"] == "demo"
    assert body["market_top_skills"] == []
    assert body["observations_count"] == 800


def test_profile_skills_and_proficiency_remain_user_isolated_without_market_evidence(monkeypatch, tmp_path):
    database = FakeFirestore({
        "users/user-a": profile_doc(
            "user-a",
            skills=["Python", "SQL"],
            levels={"Python": "Beginner", "SQL": "Expert"},
            city="Chennai",
        ),
        "users/user-b": profile_doc(
            "user-b",
            skills=["React"],
            levels={"React": "Comfortable"},
            city="Chennai",
        ),
    })
    configure_database(monkeypatch, database)
    _store_city_history(tmp_path / "market.sqlite3")

    authenticate_as("user-a")
    with TestClient(app) as client:
        first = client.get(
            "/api/v1/skills/intelligence", params={"skill": "Python"}
        ).json()
    database.documents["users/user-a"]["profile"]["skills"]["skill_levels"] = {
        "Python": "Expert",
        "SQL": "Beginner",
    }
    authenticate_as("user-a")
    with TestClient(app) as client:
        changed_proficiency = client.get(
            "/api/v1/skills/intelligence", params={"skill": "Python"}
        ).json()

    authenticate_as("user-b")
    with TestClient(app) as client:
        other_user = client.get(
            "/api/v1/skills/intelligence", params={"skill": "React"}
        ).json()

    assert first["personal_top_skills"] == []
    assert changed_proficiency["personal_top_skills"] == []
    assert first["selected_skill"]["proficiency"] == "Beginner"
    assert changed_proficiency["selected_skill"]["proficiency"] == "Expert"
    assert other_user["profile_context"]["selected_skills"] == ["React"]
    assert other_user["personal_top_skills"] == []
    assert other_user["selected_skill"]["proficiency"] == "Comfortable"
    assert "Python" not in other_user["profile_context"]["selected_skills"]


def test_location_and_range_filters_only_use_matching_stored_observations(monkeypatch, tmp_path):
    database = FakeFirestore({
        "users/user-a": profile_doc("user-a", skills=["Python"], city="Chennai")
    })
    configure_database(monkeypatch, database)
    store = _store_city_history(tmp_path / "market.sqlite3", "Chennai")
    store.insert_observations([
        MarketObservation(
            id=f"bangalore:{period}:java:{index}",
            source="jsearch",
            skill="Java",
            signal_type="demand",
            history_type="platform_collected",
            observed_at=datetime.fromisoformat(f"{period}-15T12:00:00+00:00"),
            period=period,
            location="Bangalore",
            scope="city",
            posting_id=f"bangalore:{period}:{index}",
            value=1,
            data_origin="demo",
        )
        for period in _recent_completed_periods()
        for index in range(20)
    ])
    authenticate_as()

    with TestClient(app) as client:
        city_response = client.get(
            "/api/v1/skills/intelligence",
            params={"location": "Bangalore", "range": "6m"},
        )
        short_range_response = client.get(
            "/api/v1/skills/intelligence",
            params={"location": "Chennai", "range": "30d"},
        )

    city_body = city_response.json()
    short_range_body = short_range_response.json()
    assert city_body["filters"]["location"] == "Bangalore"
    assert city_body["data_origin"] == "demo"
    assert city_body["sources_used"] == []
    assert city_body["market_top_skills"] == []
    assert city_body["observations_count"] == 80
    assert short_range_body["data_status"] == "insufficient_data"
    assert short_range_body["market_top_skills"] == []
    assert short_range_body["historical_periods_count"] < 4
    assert short_range_body["observations_count"] < 400


def test_repeated_intelligence_reads_return_the_same_backend_calculation(monkeypatch, tmp_path):
    database = FakeFirestore({
        "users/user-a": profile_doc("user-a", skills=["Python"], city="Chennai")
    })
    configure_database(monkeypatch, database)
    _store_city_history(tmp_path / "market.sqlite3")
    authenticate_as()

    with TestClient(app) as client:
        my_skills_view = client.get(
            "/api/v1/skills/intelligence",
            params={"location": "Chennai", "range": "6m"},
        ).json()
        home_view = client.get(
            "/api/v1/skills/intelligence",
            params={"location": "Chennai", "range": "6m"},
        ).json()

    assert my_skills_view["market_top_skills"] == home_view["market_top_skills"]
    assert my_skills_view["personal_top_skills"] == home_view["personal_top_skills"]
    assert my_skills_view["skill_trends"] == home_view["skill_trends"]


def test_skill_response_models_reject_unexpected_fields():
    with pytest.raises(ValueError):
        UserSkillsResponse.model_validate({"skills": [], "unexpected": True})
    with pytest.raises(ValueError):
        SkillIntelligenceResponse.model_validate({
            "profile_context": {"location": None, "selected_skills": []},
            "filters": {"location": None, "range": "6m"},
            "data_status": "unknown",
            "top_skills": [],
            "skill_trends": [],
        })


def test_single_demo_provider_period_is_not_exposed_as_production_evidence():
    from app.services.skill_intelligence_service import _build_intelligence_response

    now = datetime(2026, 10, 7, tzinfo=timezone.utc)
    item = MarketObservation(
        id="real-observation-id", source="adzuna", skill="C#", signal_type="demand",
        observed_at=now, period="2026-10", scope="country", location="India",
        posting_id="real-job-id", value=1.0, history_type="platform_collected",
        data_origin="demo", fetch_run_id="demo-run-id", series_id="adzuna:panel:job-demand:c_sharp:v1",
        query_id="adzuna:panel", panel_version="job-demand-v1",
    )
    trend_records = calculate_skill_trends([item], min_periods=4, now=now)
    response = _build_intelligence_response(
        profile={}, skills=[], display_location="India", range_key="6m", skill="C#",
        effective_location="India", observations=[item], trend_records=trend_records,
        summary={"last_collection": {"status": "success", "providers": {
            "adzuna": {"run_id": "real-run-id", "completed_at": now},
        }}}, settings=Settings(_env_file=None), pending_sources=[],
    )

    assert response.data_state == "insufficient_data"
    assert response.data_origin == "demo"
    assert response.market_top_skills == []
    assert response.current_demand == []
