from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_internal_jobs_empty_query():
    # Calling without any company or token should return empty response without error
    response = client.get("/api/v1/jobs/internal")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "empty"
    assert data["count"] == 0
    assert data["jobs"] == []

def test_internal_jobs_query_by_company():
    # Calling with real company in DB (TCS or NVIDIA)
    response = client.get("/api/v1/jobs/internal?company_name=TCS&limit=5")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "available"
    assert data["count"] > 0
    first_job = data["jobs"][0]
    assert "title" in first_job
    assert "company_name" in first_job
    assert "TCS" in first_job["company_name"]
    assert "status" in first_job
    assert "required_skills" in first_job

def test_internal_jobs_career_alias():
    response = client.get("/api/v1/career/jobs/internal?company_name=NVIDIA&limit=3")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "available"
    assert data["count"] > 0
    assert "NVIDIA" in data["jobs"][0]["company_name"]

