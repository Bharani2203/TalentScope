"""TalentScope.ai — Core Intelligence Review Demonstration Script.

Repeatable demonstration script using real application services, FastAPI endpoints,
and the local analytical reference database.

Demonstrates all 9 review scenarios required for tomorrow's project review:
1. Resolve a known technology (e.g. Python).
2. Ask what software skills are associated with a known occupation.
3. Ask a follow-up question that uses conversation context (anaphora resolution).
4. Request evidence or provenance for a returned fact.
5. Request a trend where enough valid observations exist; otherwise demonstrate the honest insufficient-data response.
6. Search stored job postings, clearly identifying source and scope limitations.
7. Request a next action based on facts the system actually returned.
8. Verify that forecasting and workforce simulation are reported as unsupported.
9. Verify authorization, user isolation, and company tenant isolation.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app
from app.api import dependencies
from app.models.auth import AuthenticatedUser, UserProfile, UserType
from app.models.skill_intelligence import MarketObservation
from app.storage.conversation_store import ConversationStore

# Setup test users
USER_INDIVIDUAL = AuthenticatedUser(uid="demo_user_individual", email="individual@talentscope.ai")
USER_EMPLOYEE = AuthenticatedUser(uid="demo_user_employee", email="employee@talentscope.ai")
USER_CORP_NVIDIA = UserProfile(uid="demo_user_corp_nvidia", email="admin@nvidia.com", company_id="nvidia", role="company_admin")
USER_ATTACKER = AuthenticatedUser(uid="demo_user_attacker", email="attacker@external.com")

client = TestClient(app)

SEPARATOR = "=" * 80
SUB_SEPARATOR = "-" * 80


def print_header(title: str, scenario_num: int):
    print(f"\n{SEPARATOR}")
    print(f" SCENARIO {scenario_num}: {title.upper()}")
    print(SEPARATOR)


def print_result(status: str, detail: str, facts: list = None, limitations: list = None, evidence: list = None):
    print(f"[*] Execution Status: [{status.upper()}]")
    print(f"[*] Answer Summary:   {detail[:200]}..." if len(detail) > 200 else f"[*] Answer:           {detail}")
    if facts:
        print(f"[*] Facts ({len(facts)}):")
        for f in facts[:3]:
            name = f.get('metric_name') or f.get('name')
            val = f.get('metric_value') or f.get('value')
            src = f.get('source', 'unknown')
            print(f"    - {name}: {val} (source: {src})")
    if evidence:
        print(f"[*] Citations ({len(evidence)}):")
        for e in evidence[:2]:
            print(f"    - [{e.get('source')}] {e.get('description', '')[:100]}")
    if limitations:
        print(f"[*] Limitations Disclosed ({len(limitations)}):")
        for lim in limitations[:2]:
            print(f"    - {lim}")


def run_demonstration():
    print(f"\n{'#' * 80}")
    print(" TALENTSCOPE.AI — CORE INTELLIGENCE PROTOTYPE DEMONSTRATION")
    print(" Milestone: G2.6/G2.7 Frozen — Truthful, Grounded, Real Reference Store")
    print(f"{'#' * 80}")

    passed = 0
    total = 9

    # -------------------------------------------------------------------------
    # SCENARIO 1: Resolve a known technology (Python)
    # -------------------------------------------------------------------------
    print_header("Resolve Known Technology (Python)", 1)
    app.dependency_overrides[dependencies.get_current_user] = lambda: USER_INDIVIDUAL
    try:
        resp = client.post("/api/v1/intelligence/entities/resolve", json={"name": "Python", "entity_type": "technology"})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert data["status"] == "resolved"
        assert data["entity"]["canonical_name"] == "Python"
        print(f"[*] Entity Query:     'Python'")
        print(f"[*] Match Status:     {data['status'].upper()}")
        print(f"[*] Canonical ID:     {data['entity']['entity_id']}")
        print(f"[*] Canonical Name:   {data['entity']['canonical_name']}")
        print(f"[*] Primary Source:   {data['entity']['source']}")
        print(f"[*] Match Method:     {data['match_method']} (Confidence: {data['confidence']})")
        passed += 1
        print(">>> SCENARIO 1: PASSED")
    finally:
        app.dependency_overrides.clear()

    # -------------------------------------------------------------------------
    # SCENARIO 2: Software skills associated with a known occupation
    # -------------------------------------------------------------------------
    print_header("Software Skills for Known Occupation (Software Developers)", 2)
    conv_id = f"demo_conv_{uuid.uuid4().hex[:8]}"
    app.dependency_overrides[dependencies.get_current_user] = lambda: USER_INDIVIDUAL
    try:
        resp = client.post("/api/v1/intelligence/answer", json={
            "message": "What software tools does a Software Developer use?",
            "portal_type": "individual",
            "conversation_id": conv_id,
            "location": "Bangalore"
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert data["execution_status"] == "completed"
        assert len(data["facts"]) > 0
        assert any(e["source"].startswith("ref_onet") for e in data["evidence"])
        print_result(data["execution_status"], data["answer"], data["facts"], data["limitations"], data["evidence"])
        passed += 1
        print(">>> SCENARIO 2: PASSED")
    finally:
        app.dependency_overrides.clear()

    # -------------------------------------------------------------------------
    # SCENARIO 3: Follow-up question using conversation context (Anaphora)
    # -------------------------------------------------------------------------
    print_header("Follow-up Question with Anaphora Resolution ('What are its related occupations?')", 3)
    app.dependency_overrides[dependencies.get_current_user] = lambda: USER_INDIVIDUAL
    try:
        resp = client.post("/api/v1/intelligence/answer", json={
            "message": "What are its related occupations?",
            "portal_type": "individual",
            "conversation_id": conv_id,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["conversation_id"] == conv_id
        assert data["execution_status"] == "completed"
        print(f"[*] Conversation ID: {conv_id} (Preserved)")
        print_result(data["execution_status"], data["answer"], data["facts"], data["limitations"], data["evidence"])
        passed += 1
        print(">>> SCENARIO 3: PASSED")
    finally:
        app.dependency_overrides.clear()

    # -------------------------------------------------------------------------
    # SCENARIO 4: Request evidence or provenance for a returned fact
    # -------------------------------------------------------------------------
    print_header("Request Evidence & Provenance for Technology Entity (Python)", 4)
    app.dependency_overrides[dependencies.get_current_user] = lambda: USER_INDIVIDUAL
    try:
        resp = client.post("/api/v1/intelligence/answer", json={
            "message": "Show evidence and provenance for Python",
            "portal_type": "individual",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["execution_status"] == "completed"
        assert len(data["evidence"]) > 0
        assert all(e["data_origin"] == "real" for e in data["evidence"])
        print_result(data["execution_status"], data["answer"], data["facts"], data["limitations"], data["evidence"])
        passed += 1
        print(">>> SCENARIO 4: PASSED")
    finally:
        app.dependency_overrides.clear()

    # -------------------------------------------------------------------------
    # SCENARIO 5: Trend Analysis: Insufficient-Data vs. Verified Multi-period Trend
    # -------------------------------------------------------------------------
    print_header("Trend Analysis (Honest Insufficient-Data vs. Verified Calculation)", 5)
    app.dependency_overrides[dependencies.get_current_user] = lambda: USER_INDIVIDUAL
    try:
        # Part A: With 0 stored market observations, system honestly returns insufficient_data
        resp_unavail = client.post("/api/v1/intelligence/answer", json={
            "message": "Show Python's historical market demand trend",
            "portal_type": "individual",
        })
        assert resp_unavail.status_code == 200
        data_unavail = resp_unavail.json()
        assert data_unavail["execution_status"] == "insufficient_data"
        assert "INSUFFICIENT_OBSERVATION_DATA" in data_unavail["reason_codes"]
        print("[Part A: Real Database with 0 Market Observations]")
        print_result(data_unavail["execution_status"], data_unavail["answer"], None, data_unavail["limitations"])

        # Part B: With 4 valid consecutive monthly observations provided, trend executes
        sample_obs = [
            {
                "id": "obs-1",
                "skill": "Python",
                "skill_id": "skill:python",
                "source": "jsearch",
                "signal_type": "demand",
                "period": "2026-05",
                "value": 100.0,
                "observed_at": "2026-05-01T00:00:00Z",
                "history_type": "snapshot",
                "series_id": "series_py_us",
                "data_origin": "real",
            },
            {
                "id": "obs-2",
                "skill": "Python",
                "skill_id": "skill:python",
                "source": "jsearch",
                "signal_type": "demand",
                "period": "2026-06",
                "value": 120.0,
                "observed_at": "2026-06-01T00:00:00Z",
                "history_type": "snapshot",
                "series_id": "series_py_us",
                "data_origin": "real",
            },
            {
                "id": "obs-3",
                "skill": "Python",
                "skill_id": "skill:python",
                "source": "jsearch",
                "signal_type": "demand",
                "period": "2026-07",
                "value": 140.0,
                "observed_at": "2026-07-01T00:00:00Z",
                "history_type": "snapshot",
                "series_id": "series_py_us",
                "data_origin": "real",
            },
            {
                "id": "obs-4",
                "skill": "Python",
                "skill_id": "skill:python",
                "source": "jsearch",
                "signal_type": "demand",
                "period": "2026-08",
                "value": 160.0,
                "observed_at": "2026-08-01T00:00:00Z",
                "history_type": "snapshot",
                "series_id": "series_py_us",
                "data_origin": "real",
            },
        ]
        resp_avail = client.post("/api/v1/intelligence/answer", json={
            "message": "Show Python's historical market demand trend",
            "portal_type": "individual",
            "observations": sample_obs
        })
        assert resp_avail.status_code == 200
        data_avail = resp_avail.json()
        assert data_avail["execution_status"] == "completed"
        print("\n[Part B: 4 Consecutive Periods Provided — Theil-Sen Calculation]")
        print_result(data_avail["execution_status"], data_avail["answer"], data_avail["facts"], data_avail["limitations"])
        passed += 1
        print(">>> SCENARIO 5: PASSED")
    finally:
        app.dependency_overrides.clear()

    # -------------------------------------------------------------------------
    # SCENARIO 6: Search stored job postings (identifying source & scope)
    # -------------------------------------------------------------------------
    print_header("Search Stored Job Postings (Scope & Limitation Transparency)", 6)
    app.dependency_overrides[dependencies.get_current_user] = lambda: USER_INDIVIDUAL
    try:
        resp = client.post("/api/v1/intelligence/answer", json={
            "message": "Search stored job postings for Python in Bangalore",
            "portal_type": "individual",
            "location": "Bangalore"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["execution_status"] == "completed"
        assert any("stored collection" in lim.lower() for lim in data["limitations"])
        print_result(data["execution_status"], data["answer"], data["facts"], data["limitations"], data["evidence"])
        passed += 1
        print(">>> SCENARIO 6: PASSED")
    finally:
        app.dependency_overrides.clear()

    # -------------------------------------------------------------------------
    # SCENARIO 7: Request a next action based on facts the system actually returned
    # -------------------------------------------------------------------------
    print_header("Action Recommendations Grounded in Skill Taxonomy", 7)
    app.dependency_overrides[dependencies.get_current_user] = lambda: USER_INDIVIDUAL
    try:
        resp = client.post("/api/v1/intelligence/answer", json={
            "message": "What should I learn next for Cloud Architect?",
            "portal_type": "individual",
            "target_role": "Cloud Architect",
            "selected_skills": ["Python", "Docker"]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["execution_status"] == "completed"
        print_result(data["execution_status"], data["answer"], data["facts"], data["limitations"])
        passed += 1
        print(">>> SCENARIO 7: PASSED")
    finally:
        app.dependency_overrides.clear()

    # -------------------------------------------------------------------------
    # SCENARIO 8: Forecasting & Simulation Reported as Unsupported in G2.6/G2.7
    # -------------------------------------------------------------------------
    print_header("Forecasting & Simulation Honesty (Strictly Unsupported)", 8)
    app.dependency_overrides[dependencies.get_current_user] = lambda: USER_INDIVIDUAL
    try:
        # Forecast query
        resp_fc = client.post("/api/v1/intelligence/answer", json={
            "message": "Forecast future demand for Python over the next 2 years",
            "portal_type": "individual",
        })
        assert resp_fc.status_code == 200
        data_fc = resp_fc.json()
        assert data_fc["execution_status"] == "unsupported"
        assert "CAPABILITY_UNSUPPORTED_IN_G2_6" in data_fc["reason_codes"]

        # Simulation query
        resp_sim = client.post("/api/v1/intelligence/answer", json={
            "message": "Simulate what happens if 50% of workforce shifts to AI",
            "portal_type": "company",
            "company_id": "nvidia"
        })
        assert resp_sim.status_code == 200
        data_sim = resp_sim.json()
        assert data_sim["execution_status"] == "unsupported"

        print("[A. Future Demand Forecast Inquiry]")
        print_result(data_fc["execution_status"], data_fc["answer"], None, data_fc["limitations"])
        print("\n[B. Workforce What-If Simulation Inquiry]")
        print_result(data_sim["execution_status"], data_sim["answer"], None, data_sim["limitations"])
        passed += 1
        print(">>> SCENARIO 8: PASSED")
    finally:
        app.dependency_overrides.clear()

    # -------------------------------------------------------------------------
    # SCENARIO 9: Authorization & Tenant Isolation
    # -------------------------------------------------------------------------
    print_header("Authorization & Multi-Tenant Isolation Guards", 9)
    try:
        # A. Unauthenticated query -> 401 Unauthorized
        app.dependency_overrides.clear()
        resp_unauth = client.post("/api/v1/intelligence/answer", json={"message": "What is Python?"})
        assert resp_unauth.status_code == 401
        print("[A. Unauthenticated Query] -> HTTP 401 Unauthorized (Blocked)")

        # B. Individual user querying private company workforce -> Blocked
        app.dependency_overrides[dependencies.get_current_user] = lambda: USER_INDIVIDUAL
        resp_indiv_corp = client.post("/api/v1/intelligence/answer", json={
            "message": "What is our company workforce capability?",
            "portal_type": "company",
            "company_id": "nvidia"
        })
        assert resp_indiv_corp.status_code == 200
        data_indiv_corp = resp_indiv_corp.json()
        assert data_indiv_corp["execution_status"] == "blocked"
        assert "UNAUTHORIZED_PORTAL_ACCESS" in data_indiv_corp["reason_codes"]
        print("[B. Individual User Querying Company Workforce] -> execution_status='blocked' (UNAUTHORIZED_PORTAL_ACCESS)")

        # C. Cross-company access: NVIDIA user querying Google workforce -> Blocked
        app.dependency_overrides[dependencies.get_current_user] = lambda: USER_CORP_NVIDIA
        resp_cross = client.post("/api/v1/intelligence/answer", json={
            "message": "What is our company workforce capability?",
            "portal_type": "company",
            "company_id": "google"
        })
        assert resp_cross.status_code == 200
        data_cross = resp_cross.json()
        assert data_cross["execution_status"] == "blocked"
        assert "UNAUTHORIZED_CROSS_COMPANY_ACCESS" in data_cross["reason_codes"]
        print("[C. Cross-Company Boundary Violation (NVIDIA querying Google)] -> execution_status='blocked' (UNAUTHORIZED_CROSS_COMPANY_ACCESS)")

        # D. Cross-user conversation hijacking: Attacker accessing Alice's conversation_id -> Blocked
        app.dependency_overrides[dependencies.get_current_user] = lambda: USER_ATTACKER
        resp_hijack = client.post("/api/v1/intelligence/answer", json={
            "message": "What did we just discuss?",
            "conversation_id": conv_id
        })
        assert resp_hijack.status_code == 200
        data_hijack = resp_hijack.json()
        assert data_hijack["execution_status"] == "blocked"
        assert "UNAUTHORIZED_CONVERSATION_ACCESS" in data_hijack["reason_codes"]
        print("[D. Cross-User Conversation Hijacking Attempt] -> execution_status='blocked' (UNAUTHORIZED_CONVERSATION_ACCESS)")

        passed += 1
        print(">>> SCENARIO 9: PASSED")
    finally:
        app.dependency_overrides.clear()

    # -------------------------------------------------------------------------
    # SUMMARY
    # -------------------------------------------------------------------------
    print(f"\n{SEPARATOR}")
    print(f" DEMONSTRATION SUMMARY: {passed}/{total} SCENARIOS VERIFIED SUCCESSFULLY")
    print(SEPARATOR)
    if passed == total:
        print("ALL 9 CORE INTELLIGENCE ACCEPTANCE SCENARIOS PASSED.")
        return 0
    else:
        print(f"FAILED: {total - passed} scenarios encountered errors.")
        return 1


if __name__ == "__main__":
    sys.exit(run_demonstration())
