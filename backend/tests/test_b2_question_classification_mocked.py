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
        ("Simulate workforce headcount changes across departments", None, "CLEAR"),
        ("Run a workforce simulation", None, "CLEAR"),
        ("Headcount what-if scenarios", None, "OFF-TOPIC"),
        ("What-if planning for the workforce", None, "CLEAR"),
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


@pytest.mark.parametrize(
    "message",
    [
        "airport timetable",
        "air quality forecast",
        "airline route delays",
        "air traffic control schedule",
        "airplane maintenance schedule",
        "aid application for college",
        "AI-generated poem about dragons",
        "simulate a chess game",
        "simulate a chess tournament",
        "what if I buy a car",
        "what if my team wins cricket",
        "headcount of a cricket team",
        "headcount of bees in a hive",
        "movie recommendations",
        "recommend a restaurant",
    ],
)
def test_mocked_off_topic_phrases_do_not_enter_scope(message):
    assert classify_question(message) == "OFF-TOPIC"


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Find data engineer jobs in Bangalore", "CLEAR"),
        ("Find python developer jobs in Chennai", "CLEAR"),
        ("What does a data engineer do?", "CLEAR"),
        ("What skills does a data engineer need?", "CLEAR"),
        ("Is Python becoming more popular?", "CLEAR"),
        ("Compare Python and Java", "CLEAR"),
        ("Give me a preparation plan for Web Developer", "CLEAR"),
        ("what is the weather", "OFF-TOPIC"),
    ],
)
def test_mocked_demo_questions_keep_their_scope_contract(message, expected):
    assert classify_question(message) == expected


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("What skills are in demand?", "CLEAR"),
        ("jobs in Bangalore", "TOO BROAD"),
        ("Which technologies are growing?", "CLEAR"),
        ("recommend some skills to learn", "CLEAR"),
        ("salaries for data engineers", "CLEAR"),
        ("What software tools does a Data Scientist use?", "CLEAR"),
        ("Tell me about Go", "CLEAR"),
    ],
)
def test_mocked_additional_in_scope_phrases(message, expected):
    assert classify_question(message) == expected


@pytest.mark.parametrize(
    "message",
    [
        "Learn Python",
        "Python roadmap for beginners",
        "Python market in India",
        "Study Java for interviews",
        "Which companies use Go?",
        "Python careers",
        "Excel skills for analysts",
        "What should I learn first, Python or Java?",
        "Is R still used for statistics jobs?",
        "Suggest a Python study plan",
    ],
)
def test_mocked_learning_and_career_questions_stay_in_scope(message):
    assert classify_question(message) == "CLEAR"


@pytest.mark.parametrize(
    "message",
    [
        "What is a banana?",
        "What is the time?",
        "What is a black hole?",
        "What is the best pizza?",
        "What is a bicycle?",
        "What is the capital of France?",
        "What is a dog?",
        "What is my favorite color?",
        "What is the weather?",
        "What is a chess opening?",
        "What is a movie review?",
        "What is a garden hose?",
    ],
)
def test_mocked_generic_what_is_questions_are_off_topic(message):
    assert classify_question(message) == "OFF-TOPIC"


@pytest.mark.parametrize(
    "message",
    [
        "Simulate what happens if 50% of workforce shifts to AI",
        "Simulate workforce reskilling scenario for our team.",
        "Simulate workforce what-if transition scenario.",
        "Simulate workforce headcount changes across departments",
        "Simulate workforce what-if transition to AI engineering.",
    ],
)
def test_mocked_workforce_simulation_phrases_remain_in_scope(message):
    assert classify_question(message) == "CLEAR"


def test_mocked_software_tools_question_is_in_scope():
    message = "What software tools does a Data Scientist use?"
    assert classify_question(message) == "CLEAR"


def test_mocked_registry_skill_classification_handles_ambiguous_names():
    assert classify_question("What is Node.js used for?") == "CLEAR"
    # Kafka remains a known limitation because it is not in the skill registry.
    assert classify_question("Tell me about Kafka.") == "OFF-TOPIC"
    assert classify_question("Java island travel tips") == "OFF-TOPIC"
    assert classify_question("Is a python a snake?") == "OFF-TOPIC"


@pytest.mark.parametrize(
    "message",
    [
        "Java skills for e-commerce shopping platforms",
        "Python developer jobs in Chennai for sports analytics",
        "Which Go skills are used in travel booking software?",
        "What Rust skills do car software engineers need?",
    ],
)
def test_mocked_ambiguous_skills_with_domain_context_stay_in_scope(message):
    assert classify_question(message) == "CLEAR"


def test_mocked_movie_recommendation_question_stays_off_topic():
    # known limitation: 'recommendation' needs a domain context
    assert classify_question("Is Python used in movie recommendation systems?") == "OFF-TOPIC"


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
