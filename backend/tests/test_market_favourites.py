import pytest
from fastapi import HTTPException

from app.models.skill_intelligence import FavouriteEntityIdsUpdateRequest
from app.services import market_favourites_service as service


class Snapshot:
    def __init__(self, data):
        self.data = data
        self.exists = data is not None

    def to_dict(self):
        return self.data


class Document:
    def __init__(self, records, uid):
        self.records = records
        self.uid = uid

    def get(self):
        return Snapshot(self.records.get(self.uid))

    def set(self, payload, merge=False):
        self.records[self.uid] = {**(self.records.get(self.uid) or {}), **payload}


class Client:
    def __init__(self, records):
        self.records = records

    def collection(self, name):
        assert name == "users"
        return self

    def document(self, uid):
        return Document(self.records, uid)


def test_market_favourites_are_user_scoped_deduplicated_and_supported(monkeypatch):
    records = {"alice": {"user_type": "individual"}, "bob": {"user_type": "individual", "preferences": {"favorite_market_entity_ids": ["company:other"]}}}
    catalog = {
        "companies_with_job_evidence": [{"entity_id": "company:acme"}],
        "technologies": [{"skill_id": "tech:rust"}],
        "registered_company": None,
    }
    monkeypatch.setattr(service, "get_firestore_client", lambda: Client(records))
    monkeypatch.setattr("app.services.intelligence_catalog_service.get_market_catalog", lambda uid: catalog)

    result = service.update_market_favourites("alice", FavouriteEntityIdsUpdateRequest(entity_ids=["company:acme", "tech:rust", "company:acme"]))

    assert result.entity_ids == ["company:acme", "tech:rust"]
    assert records["alice"]["preferences"]["favorite_market_entity_ids"] == result.entity_ids
    assert records["bob"]["preferences"]["favorite_market_entity_ids"] == ["company:other"]


def test_market_favourites_reject_unsupported_and_company_profile(monkeypatch):
    records = {"org": {"user_type": "company"}}
    monkeypatch.setattr(service, "get_firestore_client", lambda: Client(records))
    monkeypatch.setattr("app.services.intelligence_catalog_service.get_market_catalog", lambda uid: {
        "companies_with_job_evidence": [], "technologies": [], "registered_company": None,
    })
    with pytest.raises(HTTPException) as unsupported:
        service.update_market_favourites("alice", FavouriteEntityIdsUpdateRequest(entity_ids=["fake"]))
    assert unsupported.value.status_code == 422
    with pytest.raises(HTTPException) as forbidden:
        service.update_market_favourites("org", FavouriteEntityIdsUpdateRequest(entity_ids=[]))
    assert forbidden.value.status_code == 403
