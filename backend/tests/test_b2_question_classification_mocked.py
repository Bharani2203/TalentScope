"""MOCKED coverage for B2 classification, slots, options, and session persistence."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.answer_block_service import build_answer_block
from app.services.collected_posting_skills_service import compute_posting_skill_aggregate
from app.services.question_classification_service import (
    classify_question,
    merge_follow_up,
    missing_job_slot,
    next_clarification_round,
    quick_reply_options,
)
from app.storage.conversation_store import ConversationStore


@pytest.mark.parametrize(
    ("message", "state", "expected"),
    [
        ("software developer jobs", None, "TOO BROAD"),
        ("software developer jobs in Bengaluru", None, "CLEAR"),
        ("software developer jobs with Python", None, "CLEAR"),
        ("UI/UX trends", None, "CLEAR"),
        ("What is Python used for?", None, "CLEAR"),
        ("What is Terraform?", None, "CLEAR"),
        ("What should I learn next based on evidence?", None, "CLEAR"),
        ("Bengaluru", {"active": True}, "FOLLOW-UP"),
        ("Skip", {"active": True}, "FOLLOW-UP"),
        ("What is Python used for?", {"active": True}, "CLEAR"),
        ("UI/UX trends", {"active": True}, "CLEAR"),
        ("Tell me a joke", None, "OFF-TOPIC"),
        ("capital of France", None, "OFF-TOPIC"),
    ],
)
def test_mocked_four_way_question_classification(message, state, expected):
    assert classify_question(message, state) == expected


def test_mocked_follow_up_merges_location_and_technology_slots():
    state = {
        "active": True,
        "pending_slot": "location",
        "slots": {"role": "Software Developer", "location": None, "technology": None},
    }
    merged, escape = merge_follow_up(state, "Chennai, Python", known_skills=["Python"])
    assert escape is False
    assert merged == {
        "role": "Software Developer", "location": "Chennai", "technology": "Python",
        "experience_level": None,
    }
    assert missing_job_slot(merged) is None


@pytest.mark.parametrize("reply", ["Skip", "Show everything"])
def test_mocked_escape_replies_bypass_remaining_clarification(reply):
    state = {
        "active": True, "pending_slot": "location",
        "slots": {"role": "Software Developer", "location": None, "technology": None},
    }
    _, escape = merge_follow_up(state, reply)
    assert escape is True
    assert next_clarification_round(1, "location", escape) is None


def test_mocked_two_round_cap_answers_on_turn_three():
    assert next_clarification_round(1, "location", False) == 2
    assert next_clarification_round(2, "location", False) is None


def test_mocked_quick_replies_are_exactly_stored_city_options_and_clean_aliases():
    aggregate = compute_posting_skill_aggregate([
        ("1", {"source": "x", "source_job_id": "1", "country_code": "in", "location": "Bangalore, India; Mumbai, India", "skills_raw": ["Python"]}),
        ("2", {"source": "x", "source_job_id": "2", "country_code": "in", "location": "Bengaluru-VTP, India", "skills_raw": ["Python"]}),
        ("3", {"source": "x", "source_job_id": "3", "country_code": "in", "location": "Pune, India", "skills_raw": ["SQL"]}),
    ])
    assert aggregate["location_counts"] == [
        {"location": "Bengaluru", "count": 2},
        {"location": "Mumbai", "count": 1},
        {"location": "Pune", "count": 1},
    ]
    chips = quick_reply_options("location", aggregate)
    assert [chip["value"] for chip in chips] == [
        "Bengaluru", "Mumbai", "Pune", "Show everything", "Skip",
    ]
    assert [chip["value"] for chip in chips[:3]] == [
        row["location"] for row in aggregate["location_counts"]
    ]


def test_mocked_no_match_answers_plainly_and_uses_only_data_backed_alternatives():
    fact = SimpleNamespace(
        fact_type="stored_job_postings", metric_value=0,
        details={
            "postings": [],
            "no_match_alternatives": ["Python appears in Bengaluru (28 collected postings)."],
        },
    )
    block = build_answer_block(
        intent="search_jobs", user_message="Chennai Python",
        answer="No postings matched.", facts=[fact],
    )
    assert block["verdict"] == "No matching postings were found in the collected records."
    assert block["bullets"] == ["Python appears in Bengaluru (28 collected postings)."]


def test_mocked_session_state_piggybacks_on_existing_conversation_write(monkeypatch):
    writes = []

    class _Document:
        def set(self, value, merge=True):
            writes.append((value, merge))

    class _Collection:
        def document(self, _name):
            return _Document()

    class _Client:
        def collection(self, _name):
            return _Collection()

    monkeypatch.setattr("app.core.firebase.get_firestore_client", lambda: _Client())
    store = ConversationStore()
    store._conversations.clear()
    store.create_conversation(user_id="mock-user", conversation_id="b2-session-test")
    writes.clear()
    store.save_turn(
        conversation_id="b2-session-test", user_id="mock-user", user_message="software developer jobs",
        intent="search_jobs", execution_status="requires_clarification",
        session_state={"job_clarification": {"active": True, "round_count": 1}},
    )
    assert len(writes) == 1
    assert writes[0][0]["session_state"]["job_clarification"]["round_count"] == 1
    assert writes[0][1] is True


def test_mocked_session_state_reuses_access_read_without_an_extra_firestore_read(monkeypatch):
    reads = []
    from app.storage.conversation_store import ConversationState

    state_data = ConversationState(
        conversation_id="b2-existing", user_id="mock-user",
        session_state={"job_clarification": {"active": True, "round_count": 1}},
    ).model_dump(mode="json")

    class _Snapshot:
        exists = True

        def to_dict(self):
            return state_data

    class _Document:
        def get(self):
            reads.append("get")
            return _Snapshot()

    class _Collection:
        def document(self, _name):
            return _Document()

    class _Client:
        def collection(self, _name):
            return _Collection()

    monkeypatch.setattr("app.core.firebase.get_firestore_client", lambda: _Client())
    store = ConversationStore()
    store._conversations.clear()
    assert store.check_conversation_access("b2-existing", user_id="mock-user") == (True, None)
    loaded = store.get_conversation("b2-existing", user_id="mock-user")
    assert loaded.session_state == state_data["session_state"]
    assert reads == ["get"]
