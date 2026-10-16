import pytest
from fastapi import HTTPException

from app.models.skill_intelligence import FavouriteSkillsUpdateRequest
from app.services import skill_intelligence_service as service


class Snapshot:
    def __init__(self, data):
        self.data = data
        self.exists = data is not None

    def to_dict(self):
        return self.data


class FakeDocument:
    def __init__(self, records, uid):
        self.records = records
        self.uid = uid

    def get(self):
        return Snapshot(self.records.get(self.uid))

    def set(self, payload, merge=False):
        self.records[self.uid] = {**(self.records.get(self.uid) or {}), **payload}


class FakeCollection:
    def __init__(self, records):
        self.records = records

    def document(self, uid):
        return FakeDocument(self.records, uid)


class FakeClient:
    def __init__(self, records):
        self.records = records

    def collection(self, name):
        assert name == "users"
        return FakeCollection(self.records)


def test_favourites_are_uid_scoped_deduplicated_and_only_canonical(monkeypatch):
    records = {
        "alice": {"user_type": "individual", "preferences": {"favorite_skill_ids": ["python", "python", "unknown"]}},
        "bob": {"user_type": "individual", "preferences": {"favorite_skill_ids": ["java"]}},
    }
    monkeypatch.setattr(service, "get_firestore_client", lambda: FakeClient(records))
    assert service.get_favourite_skills("alice").skill_ids == ["python"]
    result = service.update_favourite_skills("alice", FavouriteSkillsUpdateRequest(skill_ids=["python", "python", "java"]))
    assert result.skill_ids == ["python", "java"]
    assert service.get_favourite_skills("bob").skill_ids == ["java"]
    assert records["bob"]["preferences"]["favorite_skill_ids"] == ["java"]


def test_favourites_reject_unknown_ids_and_non_individual_profiles(monkeypatch):
    records = {"company-user": {"user_type": "company"}}
    monkeypatch.setattr(service, "get_firestore_client", lambda: FakeClient(records))
    with pytest.raises(HTTPException) as unknown:
        service.update_favourite_skills("alice", FavouriteSkillsUpdateRequest(skill_ids=["made_up"]))
    assert unknown.value.status_code == 422
    with pytest.raises(HTTPException) as forbidden:
        service.update_favourite_skills("company-user", FavouriteSkillsUpdateRequest(skill_ids=["python"]))
    assert forbidden.value.status_code == 403
