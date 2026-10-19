from fastapi.testclient import TestClient
import pytest

from app.database.base import Base
from app.database.connection import SessionLocal
from app.database.connection import engine
from app.models.eligibility_rule import EligibilityRule
from app.models.profile import UserProfile
from app.models.scheme import Scheme
from app.services.eligibility import check_scheme_eligibility
from main import app


@pytest.fixture(autouse=True)
def isolated_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_retrieval_returns_source_attributed_evidence_and_only_recorded_criteria():
    with SessionLocal() as db:
        scheme = Scheme(
            name="Verified farm equipment assistance",
            description="Support for agricultural equipment.",
            benefit="Equipment assistance subject to official rules.",
            category="Agriculture",
            state="Karnataka",
            beneficiary_groups=["farmers"],
            source_name="Fixture source",
            source_url="https://source.example/scheme",
            verification_status="verified",
            is_active=True,
        )
        db.add(scheme)
        db.flush()
        db.add(EligibilityRule(
            scheme_id=scheme.id, field_name="state", operator="equals",
            value="Karnataka", group_id=1, logical_operator="AND",
        ))
        db.commit()
        scheme_id = scheme.id

    with TestClient(app) as client:
        response = client.get("/api/schemes/search", params={
            "q": "farm equipment", "category": "Agriculture",
            "beneficiary_group": "farmer", "state": "Karnataka",
        })
    assert response.status_code == 200
    results = response.json()["results"]
    item = next(result for result in results if result["id"] == scheme_id)
    assert item["source_name"] == "Fixture source"
    assert item["source_url"] == "https://source.example/scheme"
    assert item["verification_status"] == "verified"
    assert item["criteria_completeness"] == "recorded"
    assert item["known_criteria"] == ["state equals Karnataka (group 1, AND)"]
    assert item["evidence"][-1]["source_url"] == item["source_url"]


def test_retrieval_does_not_claim_unrecorded_criteria_or_change_eligibility():
    with SessionLocal() as db:
        scheme = Scheme(
            name="Education opportunity", description="Education support.",
            benefit="Scholarship support.", is_active=True,
        )
        db.add(scheme)
        db.commit()
        scheme_id = scheme.id
        profile = UserProfile(
            user_id=1, full_name="Test User", age=30, gender="Other", state="Karnataka"
        )
        eligibility_before = check_scheme_eligibility(profile, scheme)

    with TestClient(app) as client:
        response = client.get("/api/schemes/search", params={"q": "scholarship"})
    assert response.status_code == 200
    item = next(result for result in response.json()["results"] if result["id"] == scheme_id)
    assert item["known_criteria"] == []
    assert item["criteria_completeness"] == "not_recorded"
    assert item["eligibility_rules"] == []
    with SessionLocal() as db:
        retrieved_scheme = db.get(Scheme, scheme_id)
        assert check_scheme_eligibility(profile, retrieved_scheme) == eligibility_before
