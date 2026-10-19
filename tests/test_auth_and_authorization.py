from fastapi.testclient import TestClient
import pytest

from app.database.base import Base
from app.database.connection import engine
from conftest import TEST_DATABASE
from main import app


@pytest.fixture(autouse=True)
def database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if TEST_DATABASE.exists():
        TEST_DATABASE.unlink()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def register(client: TestClient, email: str, password: str = "correct-horse-battery-staple"):
    return client.post("/api/auth/register", json={"email": email, "password": password})


def login(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "correct-horse-battery-staple"},
    )
    assert response.status_code == 200
    assert response.json()["expires_in"] == 3_600
    return response.json()["access_token"]


def scheme_payload() -> dict:
    return {
        "name": "Education support",
        "description": "Support for eligible students.",
        "benefit": "Annual grant",
    }


def test_registration_login_and_authenticated_user(client: TestClient):
    response = register(client, "member@example.com")
    assert response.status_code == 201
    assert response.json()["is_admin"] is False

    token = login(client, "MEMBER@example.com")
    response = client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "member@example.com"


def test_missing_or_invalid_token_is_rejected(client: TestClient):
    assert client.get("/api/users/me").status_code == 401
    response = client.get("/api/users/me", headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 401


def test_only_admin_can_change_scheme_data(client: TestClient):
    register(client, "member@example.com")
    member_token = login(client, "member@example.com")
    response = client.post(
        "/api/schemes",
        json=scheme_payload(),
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert response.status_code == 403

    response = register(client, "admin@example.com")
    assert response.status_code == 201
    assert response.json()["is_admin"] is True
    admin_token = login(client, "admin@example.com")
    response = client.post(
        "/api/schemes",
        json=scheme_payload(),
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201


def test_registration_enforces_password_length_and_normalized_email(client: TestClient):
    assert register(client, "person@example.com", "short").status_code == 422
    assert register(client, "Person@Example.com").status_code == 201
    assert register(client, "person@example.com").status_code == 409


def test_authenticated_user_can_change_password(client: TestClient):
    register(client, "change@example.com")
    token = login(client, "change@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    assert client.post("/api/auth/change-password", headers=headers, json={
        "current_password": "wrong-password-value", "new_password": "new-correct-password",
    }).status_code == 400
    assert client.post("/api/auth/change-password", headers=headers, json={
        "current_password": "correct-horse-battery-staple", "new_password": "new-correct-password",
    }).status_code == 204
    assert client.post("/api/auth/login", json={
        "email": "change@example.com", "password": "correct-horse-battery-staple",
    }).status_code == 401
    assert client.post("/api/auth/login", json={
        "email": "change@example.com", "password": "new-correct-password",
    }).status_code == 200


def test_only_admin_can_create_update_or_delete_eligibility_rules(client: TestClient):
    register(client, "member@example.com")
    member_token = login(client, "member@example.com")
    register(client, "admin@example.com")
    admin_token = login(client, "admin@example.com")

    scheme_response = client.post(
        "/api/schemes",
        json=scheme_payload(),
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert scheme_response.status_code == 201
    scheme_id = scheme_response.json()["id"]
    rule_payload = {
        "field_name": "age",
        "operator": "gte",
        "value": "18",
        "group_id": 1,
        "logical_operator": "AND",
    }
    member_headers = {"Authorization": f"Bearer {member_token}"}
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    denied_create = client.post(
        f"/api/schemes/{scheme_id}/rules", json=rule_payload, headers=member_headers
    )
    assert denied_create.status_code == 403

    created = client.post(
        f"/api/schemes/{scheme_id}/rules", json=rule_payload, headers=admin_headers
    )
    assert created.status_code == 201
    rule_id = created.json()["id"]

    denied_update = client.put(
        f"/api/schemes/{scheme_id}/rules/{rule_id}", json=rule_payload, headers=member_headers
    )
    assert denied_update.status_code == 403
    updated_payload = {**rule_payload, "value": "21"}
    updated = client.put(
        f"/api/schemes/{scheme_id}/rules/{rule_id}", json=updated_payload, headers=admin_headers
    )
    assert updated.status_code == 200
    assert updated.json()["value"] == "21"

    denied_delete = client.delete(
        f"/api/schemes/{scheme_id}/rules/{rule_id}", headers=member_headers
    )
    assert denied_delete.status_code == 403
    deleted = client.delete(
        f"/api/schemes/{scheme_id}/rules/{rule_id}", headers=admin_headers
    )
    assert deleted.status_code == 204


def test_general_scheme_metadata_and_fisher_eligibility_are_exposed(client: TestClient):
    register(client, "admin@example.com")
    admin_token = login(client, "admin@example.com")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    created = client.post(
        "/api/schemes",
        headers=admin_headers,
        json={
            **scheme_payload(),
            "category": "Agriculture, Rural & Environment",
            "subcategory": "Fisheries",
            "government_level": "central",
            "ministry": "Department of Fisheries",
            "beneficiary_groups": ["marine fishers", "inland fishers"],
            "source_url": "https://example.gov/scheme",
            "source_name": "Official portal",
            "verification_status": "unverified",
        },
    )
    assert created.status_code == 201
    scheme_data = created.json()
    assert scheme_data["beneficiary_groups"] == ["marine fishers", "inland fishers"]
    assert scheme_data["government_level"] == "central"
    scheme_id = scheme_data["id"]

    rule_payload = {
        "field_name": "fisher_activity",
        "operator": "equals",
        "value": "marine",
        "group_id": 1,
        "logical_operator": "AND",
    }
    assert client.post(f"/api/schemes/{scheme_id}/rules", json=rule_payload, headers=admin_headers).status_code == 201

    register(client, "fisher@example.com")
    fisher_token = login(client, "fisher@example.com")
    fisher_headers = {"Authorization": f"Bearer {fisher_token}"}
    profile_response = client.post(
        "/api/profile",
        headers=fisher_headers,
        json={
            "full_name": "Test Fisher", "age": 35, "gender": "Other", "state": "Tamil Nadu",
            "occupation": "Fisher", "beneficiary_group": "fisher", "fisher_activity": "Marine",
        },
    )
    assert profile_response.status_code == 201
    result = client.get("/api/eligibility/matches", headers=fisher_headers)
    assert result.status_code == 200
    match = next(item for item in result.json() if item["id"] == scheme_id)
    assert match["eligible"] is False
    assert any("not confirmed" in reason.casefold() for reason in match["reasons"])
    assert match["government_level"] == "central"
    assert match["subcategory"] == "Fisheries"
    assert match["beneficiary_groups"] == ["marine fishers", "inland fishers"]
    assert match["source_url"] == "https://example.gov/scheme"


def test_general_scheme_metadata_validation(client: TestClient):
    register(client, "admin@example.com")
    token = login(client, "admin@example.com")
    response = client.post(
        "/api/schemes",
        headers={"Authorization": f"Bearer {token}"},
        json={**scheme_payload(), "government_level": "global"},
    )
    assert response.status_code == 422
