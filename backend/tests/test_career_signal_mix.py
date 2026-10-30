from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_career_signal_mix_endpoints():
    """Verify dynamic 100% normalized signal mix across different roles."""
    roles_to_test = ["Data Scientist", "AI Engineer", "Python Developer"]
    distributions = {}

    for role in roles_to_test:
        resp = client.get(f"/api/career-intelligence/signal-mix?role={role}")
        assert resp.status_code == 200, f"Failed for {role}: {resp.text}"
        data = resp.json()

        assert "role" in data
        assert "signalMix" in data
        assert "signalBreakdown" in data
        assert data["total"] == 100

        mix = data["signalMix"]
        assert len(mix) == 4, f"Expected 4 signals, got {len(mix)}"

        keys = [item["key"] for item in mix]
        assert "open_role_activity" in keys
        assert "hiring_company_activity" in keys
        assert "role_demand_momentum" in keys
        assert "workforce_reduction_signal" in keys

        pct_sum = sum(item["percent"] for item in mix)
        assert pct_sum == 100, f"Signal mix for {role} sums to {pct_sum}, expected 100"

        # Signal breakdown matches percent values
        bd = data["signalBreakdown"]
        assert bd["open_role_activity"] + bd["hiring_company_activity"] + bd["role_demand_momentum"] + bd["workforce_reduction_signal"] == 100

        distributions[role] = bd

    # Ensure dynamic signal values differ between roles (not static hardcoded identical values)
    assert distributions["Data Scientist"]["open_role_activity"] != distributions["AI Engineer"]["open_role_activity"]
    assert distributions["Python Developer"]["hiring_company_activity"] != distributions["AI Engineer"]["hiring_company_activity"]


def test_career_roles_endpoint_and_smoothed_history():
    """Verify /api/career-intelligence/roles returns dynamic signalMix and smooth historical curve."""
    resp = client.get("/api/career-intelligence/roles")
    assert resp.status_code == 200
    roles = resp.json()
    assert len(roles) > 0

    for role in roles:
        # Check signalMix presence and 100% sum
        assert "signalMix" in role
        mix = role["signalMix"]
        assert len(mix) == 4
        assert sum(s["percent"] for s in mix) == 100

        # Check history length and smooth transition to demandScore (no plunge to 45)
        hist = role["history"]
        demand_score = role["demandScore"]
        assert len(hist) == 7
        assert hist[-1] == demand_score, f"Role {role['name']} history[-1]={hist[-1]} != demandScore={demand_score}"
        # No artificial plunge on final step before projection
        assert hist[-1] >= 60

