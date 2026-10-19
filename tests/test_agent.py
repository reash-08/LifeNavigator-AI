import pytest
import json
from pathlib import Path
from fastapi.testclient import TestClient

from app.database.base import Base
from app.database.connection import SessionLocal, engine
from app.models.eligibility_rule import EligibilityRule
from app.models.profile import UserProfile
from app.models.scheme import Scheme
from app.models.scheme_source import SchemeSource
from app.services.agent import extract_intent, run_agent
from app.services.document_ingestion import ingest_document
from main import app


@pytest.fixture(autouse=True)
def isolated_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _user(client):
    assert client.post("/api/auth/register", json={"email": "agent@example.com", "password": "correct-horse-battery-staple"}).status_code == 201
    response = client.post("/api/auth/login", json={"email": "agent@example.com", "password": "correct-horse-battery-staple"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _scheme():
    scheme = Scheme(name="Karnataka farmer solar pump grant", description="Grant support for farmer solar pumps.",
        benefit="Solar pump grant", category="Agriculture, Rural & Environment", state="Karnataka",
        beneficiary_groups=["farmers"], source_name="Official Agriculture Portal",
        source_url="https://agriculture.example.gov/schemes/pump", verification_status="verified",
        eligibility_verification_status="verified", is_active=True)
    with SessionLocal() as db:
        source = SchemeSource(source_name="Official Agriculture Portal", source_url=scheme.source_url,
            provider="Agriculture Department", source_type="official_portal", is_active=True)
        db.add(source)
        db.flush()
        scheme.source_id = source.id
        db.add(scheme)
        db.flush()
        db.add(EligibilityRule(scheme_id=scheme.id, field_name="age", operator="gte", value="18", group_id=1, logical_operator="AND"))
        db.commit()
        scheme_id = scheme.id
        ingest_document(db, scheme_id=scheme_id, source_name="Official Pump Guideline",
            source_url="https://agriculture.example.gov/guidelines/pump", text="Karnataka farmers may apply for a solar pump grant.")
    return scheme_id


def test_intent_routes_discovery_and_eligibility_queries():
    assert extract_intent("Find farmer schemes in Karnataka").kind == "discovery"
    intent = extract_intent("Am I eligible for farmer support in Karnataka?")
    assert intent.kind == "eligibility" and intent.state == "Karnataka" and intent.beneficiary_group == "farmer"


def test_end_to_end_eligibility_uses_structured_rules_and_cites_sources():
    scheme_id = _scheme()
    with TestClient(app) as client:
        headers = _user(client)
        assert client.post("/api/profile", headers=headers, json={"full_name": "Test Farmer", "age": 25, "gender": "Other", "state": "Karnataka", "beneficiary_group": "farmer"}).status_code == 201
        response = client.post("/api/agent/query", headers=headers, json={"query": "Am I eligible for farmer solar pump grant in Karnataka?"})
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "eligibility" and not body["insufficient_evidence"]
    result = next(item for item in body["schemes"] if item["scheme_id"] == scheme_id)
    assert result["eligibility"] == "eligible"
    assert any("age gte 18" in reason for reason in result["eligibility_reasons"])
    assert any(source["source_url"] == "https://agriculture.example.gov/guidelines/pump" for source in body["sources"])
    assert all(source["source_id"] and source["text"] for source in body["sources"])
    assert len({source["source_id"] for source in body["sources"]}) == len(body["sources"])


def test_eligibility_never_claimed_without_user_profile():
    _scheme()
    with TestClient(app) as client:
        headers = _user(client)
        body = client.post("/api/agent/query", headers=headers, json={"query": "Am I eligible for farmer solar pump grant in Karnataka?"}).json()
    assert any(item["eligibility"] == "profile_required" for item in body["schemes"])


def test_missing_rule_fields_are_reported_as_unconfirmed():
    scheme = Scheme(name="Income based farm assistance", description="Income-based farmer assistance.",
        benefit="Assistance", source_name="Official source", source_url="https://official.example/scheme", is_active=True)
    with SessionLocal() as db:
        db.add(scheme)
        db.flush()
        db.add(EligibilityRule(scheme_id=scheme.id, field_name="annual_income", operator="lte", value="50000"))
        db.add(UserProfile(user_id=999, full_name="Test Farmer", age=25, gender="Other", state="Karnataka"))
        db.commit()
        result = run_agent(db, query="Am I eligible for income based farm assistance", profile=db.query(UserProfile).filter_by(user_id=999).one())
    assert result.schemes and result.schemes[0].eligibility == "not_confirmed"


def test_ambiguous_and_unsupported_requests_fail_closed():
    with TestClient(app) as client:
        headers = _user(client)
        ambiguous = client.post("/api/agent/query", headers=headers, json={"query": "help"}).json()
        unsupported = client.post("/api/agent/query", headers=headers, json={"query": "Find a moon colony relocation subsidy"}).json()
    assert ambiguous["needs_clarification"] and ambiguous["insufficient_evidence"]
    assert unsupported["insufficient_evidence"] and unsupported["schemes"] == [] and unsupported["sources"] == []
    assert "not find enough" in unsupported["answer"]


def test_agent_endpoint_requires_authentication():
    with TestClient(app) as client:
        assert client.post("/api/agent/query", json={"query": "Find farmer support"}).status_code == 401
        assert client.post("/api/agent/query", headers={"Authorization": "Bearer invalid"}, json={"query": "Find farmer support"}).status_code == 401


def test_agent_rejects_malformed_and_non_substantive_inputs():
    with TestClient(app) as client:
        headers = _user(client)
        for payload in (
            {},
            {"query": "   "},
            {"query": "..."},
            {"query": "Find farmer support", "unexpected": True},
            {"query": "x" * 501},
            {"query": 42},
        ):
            assert client.post("/api/agent/query", headers=headers, json=payload).status_code == 422


def test_agent_uses_only_requesting_users_profile():
    _scheme()
    with TestClient(app) as client:
        first = _user(client)
        assert client.post("/api/profile", headers=first, json={
            "full_name": "First Farmer", "age": 25, "gender": "Other", "state": "Karnataka",
        }).status_code == 201
        client.post("/api/auth/register", json={"email": "second@example.com", "password": "correct-horse-battery-staple"})
        second_login = client.post("/api/auth/login", json={"email": "second@example.com", "password": "correct-horse-battery-staple"})
        second = {"Authorization": f"Bearer {second_login.json()['access_token']}"}
        body = client.post("/api/agent/query", headers=second, json={
            "query": "Am I eligible for farmer solar pump grant in Karnataka?",
        }).json()
    assert all(item["eligibility"] == "profile_required" for item in body["schemes"])


def test_unattributed_evidence_does_not_become_a_grounded_answer():
    with SessionLocal() as db:
        db.add(Scheme(name="Local farm tool support", description="Support for farm tools.",
            benefit="Tool support", source_name="Unlinked source", source_url=None, is_active=True))
        db.commit()
        body = run_agent(db, query="Find local farm tool support", profile=None)
    assert body.insufficient_evidence
    assert "not find enough" in body.answer


def test_evaluation_fixtures_cover_measurable_agent_behaviors():
    fixtures = json.loads((Path(__file__).parent / "agent_evaluation.json").read_text(encoding="utf-8"))
    assert {item["id"] for item in fixtures} == {
        "karnataka_farm_discovery", "karnataka_farm_eligibility", "ambiguous_request", "unsupported_claim",
    }
    assert all(item.get("eligibility_authority") == "structured_rules_only"
               for item in fixtures if item["expected_intent"] == "eligibility")
    assert sum(bool(item.get("requires_cited_source")) for item in fixtures) == 2


def test_agent_evaluation_metrics_on_recorded_scheme_fixture():
    _scheme()
    with TestClient(app) as client:
        headers = _user(client)
        assert client.post("/api/profile", headers=headers, json={
            "full_name": "Evaluation Farmer", "age": 25, "gender": "Other", "state": "Karnataka",
            "beneficiary_group": "farmer",
        }).status_code == 201
        fixtures = json.loads((Path(__file__).parent / "agent_evaluation.json").read_text(encoding="utf-8"))
        observations = []
        for item in fixtures:
            body = client.post("/api/agent/query", headers=headers, json={"query": item["query"]}).json()
            observations.append((item, body))

    relevant = retrieved = 0
    cited = cited_with_provenance = 0
    eligibility_expected = eligibility_consistent = 0
    behavior_expected = behavior_passed = 0
    for item, body in observations:
        assert body["intent"] == item["expected_intent"]
        terms = item.get("expected_scheme_terms", [])
        relevant += len(terms)
        returned_names = " ".join(result["name"] for result in body["schemes"]).casefold()
        retrieved += sum(term.casefold() in returned_names for term in terms)
        if item.get("requires_cited_source"):
            cited += 1
            cited_with_provenance += bool(body["sources"]) and all(
                source["text"].strip() and source["source_name"] and source["source_url"]
                for source in body["sources"]
            )
        if "expected_eligibility" in item:
            eligibility_expected += 1
            eligibility_consistent += any(
                result["eligibility"] == item["expected_eligibility"] for result in body["schemes"]
            )
        if any(key.startswith("expected_") for key in item if key not in {
            "expected_intent", "expected_scheme_terms", "expected_eligibility",
        }):
            behavior_expected += 1
            passed = all(
                body[{"expected_clarification": "needs_clarification",
                      "expected_insufficient_evidence": "insufficient_evidence"}[key]] == expected
                for key, expected in item.items()
                if key in {"expected_clarification", "expected_insufficient_evidence"}
            )
            passed = passed and (not item.get("expected_no_schemes") or not body["schemes"])
            passed = passed and (not item.get("expected_no_sources") or not body["sources"])
            behavior_passed += passed

    metrics = {
        "retrieval_term_recall": retrieved / relevant,
        "source_attribution_rate": cited_with_provenance / cited,
        "eligibility_consistency": eligibility_consistent / eligibility_expected,
        "response_behavior_rate": behavior_passed / behavior_expected,
    }
    assert metrics == {
        "retrieval_term_recall": 1.0,
        "source_attribution_rate": 1.0,
        "eligibility_consistency": 1.0,
        "response_behavior_rate": 1.0,
    }


def test_provider_only_receives_source_backed_excerpts():
    _scheme()
    class CaptureProvider:
        def explain(self, *, question, evidence, eligibility=None):
            assert evidence and all(item["source_name"] for item in evidence)
            assert all("moon colony" not in item["text"].casefold() for item in evidence)
            return "Grounded answer"
    with SessionLocal() as db:
        body = run_agent(db, query="Find farmer solar pump grant in Karnataka", profile=None, provider=CaptureProvider())
    assert body.answer == "Grounded answer"
