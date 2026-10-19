import pytest
from fastapi.testclient import TestClient

from app.database.base import Base
from app.database.connection import engine
from main import app


@pytest.fixture(autouse=True)
def isolated_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def register(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "correct-horse-battery-staple"},
    )
    assert response.status_code == 201


def login(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "correct-horse-battery-staple"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_generalized_scheme_retrieval_keeps_provenance_and_dynamic_eligibility():
    with TestClient(app) as client:
        register(client, "admin@example.com")
        admin_headers = {"Authorization": f"Bearer {login(client, 'admin@example.com')}"}
        created = client.post(
            "/api/schemes",
            headers=admin_headers,
            json={
                "name": "Verified disability assistive-device support",
                "description": "Support delivered under official guidelines.",
                "benefit": "Assistive-device support, subject to programme criteria.",
                "category": "Disability",
                "subcategory": "Assistive devices",
                "government_level": "central",
                "ministry": "Ministry of Social Justice and Empowerment",
                "department": "Department of Empowerment of Persons with Disabilities",
                "beneficiary_groups": ["persons with disabilities"],
                "source_name": "Official scheme page",
                "source_url": "https://depwd.gov.in/en/adip-scheme/",
                "verification_status": "verified",
                "eligibility_verification_status": "verified",
                "verified_at": "2026-10-02",
            },
        )
        assert created.status_code == 201
        scheme_id = created.json()["id"]
        rule = client.post(
            f"/api/schemes/{scheme_id}/rules",
            headers=admin_headers,
            json={
                "field_name": "has_disability",
                "operator": "equals",
                "value": "true",
                "group_id": 1,
                "logical_operator": "AND",
            },
        )
        assert rule.status_code == 201

        register(client, "beneficiary@example.com")
        beneficiary_headers = {
            "Authorization": f"Bearer {login(client, 'beneficiary@example.com')}"
        }
        profile = client.post(
            "/api/profile",
            headers=beneficiary_headers,
            json={
                "full_name": "Test Beneficiary", "age": 34, "gender": "Other",
                "state": "Karnataka", "has_disability": True,
            },
        )
        assert profile.status_code == 201

        matches = client.get("/api/eligibility/matches", headers=beneficiary_headers)
        assert matches.status_code == 200
        match = next(item for item in matches.json() if item["id"] == scheme_id)
        assert match["eligible"] is True
        assert match["category"] == "Disability"
        assert match["subcategory"] == "Assistive devices"
        assert match["government_level"] == "central"
        assert match["source_name"] == "Official scheme page"
        assert match["source_url"] == "https://depwd.gov.in/en/adip-scheme/"
        assert match["verification_status"] == "verified"
        assert match["verified_at"] == "2026-10-02"
