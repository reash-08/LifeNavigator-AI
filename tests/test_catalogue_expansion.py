"""Tests for catalogue expansion to >= 100 verified government schemes.

Validates verification standards, authoritative sources, metadata completeness,
status handling (active/inactive/expired), idempotent imports, retrieval,
agent RAG citations, and abstention on insufficient evidence.
"""
from datetime import date
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database.base import Base
from app.models.user import User
from app.models.eligibility_rule import EligibilityRule
from app.models.profile import UserProfile
from app.models.scheme import Scheme
from app.models.scheme_source import SchemeSource, SchemeVersion
from app.services.agent import run_agent
from app.services.eligibility import check_scheme_eligibility
from app.services.retrieval import search_schemes
from app.services.scheme_sync import is_official_source_url, sync_records
from scripts.seed_schemes import DATASET_PATH, load_dataset, import_records, ingest_scheme_docs


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_catalogue_contains_at_least_100_verified_schemes_with_authoritative_urls():
    """Requirement: Catalogue must contain at least 100 verified records with valid authoritative source URLs."""
    dataset = load_dataset(DATASET_PATH)
    verified_schemes = [s for s in dataset.schemes if s.verification_status == "verified"]

    assert len(verified_schemes) >= 100, f"Expected at least 100 verified schemes, found {len(verified_schemes)}"

    for scheme in verified_schemes:
        assert scheme.verified_at is not None, f"Verified scheme {scheme.name} missing verified_at date"
        assert is_official_source_url(scheme.source_url), f"Scheme {scheme.name} has non-authoritative URL: {scheme.source_url}"
        assert scheme.source_url.startswith("https://"), f"Scheme {scheme.name} must use HTTPS: {scheme.source_url}"
        assert scheme.source_name and len(scheme.source_name.strip()) > 0


def test_verification_metadata_and_evidence_completeness():
    """Requirement: Verification metadata, benefits, documents, and application procedure are stored."""
    dataset = load_dataset(DATASET_PATH)
    verified_schemes = [s for s in dataset.schemes if s.verification_status == "verified"]

    for scheme in verified_schemes:
        assert len(scheme.name.strip()) >= 3, f"Scheme {scheme.name} has invalid name"
        assert len(scheme.description.strip()) >= 10, f"Scheme {scheme.name} has insufficient description"
        assert len(scheme.benefit.strip()) >= 5, f"Scheme {scheme.name} has insufficient benefit description"
        assert len(scheme.beneficiary_groups) >= 1, f"Scheme {scheme.name} must specify beneficiary groups"
        assert scheme.government_level in {"central", "state"}, f"Scheme {scheme.name} invalid gov level: {scheme.government_level}"

        if scheme.government_level == "state":
            assert scheme.state and len(scheme.state.strip()) > 0, f"State scheme {scheme.name} must specify state"

        # Check that application information is actionable where provided
        if scheme.application_url:
            assert scheme.application_url.startswith("https://"), f"Scheme {scheme.name} application URL must be HTTPS"


def test_honest_verification_statuses_and_expired_schemes():
    """Requirement: Accurate verification statuses: verified, pending, and expired/inactive."""
    dataset = load_dataset(DATASET_PATH)

    # Check for expired scheme (PMVVY sunset March 31, 2023)
    pmvvy = next((s for s in dataset.schemes if "Pradhan Mantri Vaya Vandana Yojana" in s.name), None)
    assert pmvvy is not None, "PMVVY should be in catalogue"
    assert pmvvy.verification_status == "expired", "PMVVY must be marked expired"
    assert pmvvy.is_active is False, "PMVVY must be inactive"
    assert pmvvy.effective_until == date(2023, 3, 31)

    # Check for inactive scheme (AVYAY undergoing restructuring)
    avyay = next((s for s in dataset.schemes if "Atal Vayo Abhyuday Yojana" in s.name), None)
    assert avyay is not None
    assert avyay.is_active is False, "AVYAY must be marked inactive"

    # Check for pending schemes (awaiting fresh operational circulars)
    pending_schemes = [s for s in dataset.schemes if s.verification_status == "pending"]
    assert len(pending_schemes) >= 1, "Must honestly track pending schemes"
    for pending in pending_schemes:
        assert pending.verified_at is None, "Pending schemes must not have verified_at"


def test_duplicate_detection_and_idempotent_reimport(db: Session):
    """Requirement: Idempotent imports and duplicate rejection."""
    dataset = load_dataset(DATASET_PATH)

    # First import
    summary1 = sync_records(db, dataset.schemes, apply=True, verify_curated=True)
    db.commit()
    assert summary1.added == len(dataset.schemes)
    initial_count = db.query(Scheme).count()
    assert initial_count == len(dataset.schemes)

    # Second import (exact duplicate batch)
    summary2 = sync_records(db, dataset.schemes, apply=True, verify_curated=True)
    db.commit()
    assert summary2.added == 0
    assert summary2.unchanged == len(dataset.schemes)
    assert db.query(Scheme).count() == initial_count, "Scheme count must not increase on re-import"


def test_active_and_inactive_status_filtering_in_retrieval(db: Session):
    """Requirement: Active vs inactive status handling during search/retrieval."""
    dataset = load_dataset(DATASET_PATH)
    sync_records(db, dataset.schemes, apply=True, verify_curated=True)
    db.commit()

    # Search for senior citizen schemes with active_only=True
    active_senior = search_schemes(db, "senior citizen pension", active_only=True, limit=50)
    active_names = [s.name for s in active_senior]
    assert "Pradhan Mantri Vaya Vandana Yojana (PMVVY)" not in active_names
    assert "Atal Vayo Abhyuday Yojana (AVYAY)" not in active_names
    assert any("Indira Gandhi National Old Age Pension Scheme" in name for name in active_names)

    # Search with active_only=False should include expired/inactive
    all_senior = search_schemes(db, "Vaya Vandana", active_only=False, limit=50)
    all_names = [s.name for s in all_senior]
    assert any("Pradhan Mantri Vaya Vandana Yojana" in name for name in all_names)


def test_retrieval_and_citations_for_newly_imported_schemes(db: Session):
    """Requirement: Newly imported schemes are retrievable with grounded citations."""
    dataset = load_dataset(DATASET_PATH)
    sync_records(db, dataset.schemes, apply=True, verify_curated=True)
    ingest_scheme_docs(db, dataset.schemes)
    db.commit()

    # Test retrieval of newly imported central agriculture scheme
    agri_results = search_schemes(db, "Kisan Credit Card crop loan", limit=5)
    assert len(agri_results) > 0
    kcc = next((s for s in agri_results if "Kisan Credit Card" in s.name), None)
    assert kcc is not None
    assert kcc.source_url.startswith("https://")
    assert kcc.verification_status == "verified"
    assert any(ev.kind == "document_chunk" or ev.kind == "scheme_metadata" for ev in kcc.evidence)

    # Test retrieval of newly imported state scheme (Tamil Nadu)
    tn_results = search_schemes(db, "Kalaignar Magalir Urimai Thittam", state="Tamil Nadu", limit=5)
    assert len(tn_results) > 0
    kmut = next((s for s in tn_results if "Kalaignar Magalir Urimai Thittam" in s.name), None)
    assert kmut is not None
    assert kmut.state == "Tamil Nadu"
    assert kmut.source_url == "https://kmut.tn.gov.in/"


def test_agent_generates_grounded_answer_with_citations(db: Session):
    """Requirement: AI agent produces grounded answers citing official government URLs."""
    dataset = load_dataset(DATASET_PATH)
    sync_records(db, dataset.schemes, apply=True, verify_curated=True)
    ingest_scheme_docs(db, dataset.schemes)
    db.commit()

    response = run_agent(db, query="scholarship for higher education student", profile=None)
    assert response.insufficient_evidence is False
    assert len(response.schemes) > 0
    assert len(response.sources) > 0
    for src in response.sources:
        assert src.source_url.startswith("https://")
        assert is_official_source_url(src.source_url)


def test_agent_abstains_on_insufficient_evidence(db: Session):
    """Requirement: Agent must abstain and state clarification/evidence needed if no source exists."""
    dataset = load_dataset(DATASET_PATH)
    sync_records(db, dataset.schemes, apply=True, verify_curated=True)
    db.commit()

    # Query for completely non-existent / out-of-domain concept
    response = run_agent(db, query="quantum blockchain token cryptocurrency staking rewards", profile=None)
    assert response.insufficient_evidence is True
    assert "could not find enough source-backed information" in response.answer.casefold()


def test_preservation_of_user_profiles_and_existing_rules(db: Session):
    """Requirement: Import must preserve user profiles, existing eligibility rules, and scheme history."""
    # Create existing user and profile
    user = User(id=1, email="prior_test@example.com", password_hash="dummy_hash")
    db.add(user)
    db.flush()
    profile = UserProfile(
        user_id=1,
        full_name="Prior Test User",
        age=35,
        gender="Female",
        state="Tamil Nadu",
        annual_income=150000,
        occupation="farmer",
        category="General",
    )
    db.add(profile)

    # Create existing custom scheme with rule
    custom_scheme = Scheme(
        name="Custom Pre-existing Scheme",
        description="Pre-existing custom scheme",
        benefit="Pre-existing benefit",
        category="Agriculture",
        is_active=True,
    )
    db.add(custom_scheme)
    db.flush()

    rule = EligibilityRule(
        scheme_id=custom_scheme.id,
        field_name="age",
        operator="gte",
        value="18",
        is_active=True,
    )
    db.add(rule)
    db.commit()

    # Now run import
    dataset = load_dataset(DATASET_PATH)
    sync_records(db, dataset.schemes, apply=True, verify_curated=True)
    db.commit()

    # Verify existing profile is untouched
    saved_profile = db.scalar(select(UserProfile).where(UserProfile.user_id == 1))
    assert saved_profile is not None
    assert saved_profile.full_name == "Prior Test User"
    assert saved_profile.annual_income == 150000

    # Verify custom scheme and rule are untouched
    saved_scheme = db.scalar(select(Scheme).where(Scheme.name == "Custom Pre-existing Scheme"))
    assert saved_scheme is not None
    assert len(saved_scheme.eligibility_rules) == 1
    assert saved_scheme.eligibility_rules[0].field_name == "age"
    assert saved_scheme.eligibility_rules[0].is_active is True
