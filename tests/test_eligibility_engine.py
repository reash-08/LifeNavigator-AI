from types import SimpleNamespace
from datetime import date, timedelta
from pathlib import Path
import pytest
from dotenv import dotenv_values
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.eligibility_rule import EligibilityRule
from app.models.profile import UserProfile
from app.models.scheme import Scheme
from app.models.scheme_source import SchemeSource
from app.models.user import User
from app.schemas.eligibility import EligibleSchemeResponse
from app.services.auth_service import hash_password
from app.services.eligibility import check_scheme_eligibility, EligibilityAssessment
from app.services.jwt_service import create_access_token
from app.database.base import Base
from app.database.connection import engine, SessionLocal
from fastapi.testclient import TestClient
from main import app


def get_live_db_session():
    env_path = Path(__file__).resolve().parents[1] / "backend" / ".env"
    env_vars = dotenv_values(env_path)
    db_url = env_vars.get("DATABASE_URL")
    engine = create_engine(db_url)
    return Session(engine)


def profile(**overrides):
    values = {"full_name": "Test User", "age": 21, "gender": "Other", "state": "Karnataka"}
    values.update(overrides)
    return UserProfile(**values)


def rule(field_name, operator, value, group_id=1, logical_operator="AND"):
    return EligibilityRule(
        field_name=field_name,
        operator=operator,
        value=value,
        group_id=group_id,
        logical_operator=logical_operator,
    )


def scheme(*rules, active=True):
    source_url = "https://schemes.gov.in/official"
    source = SimpleNamespace(is_active=True, source_url=source_url)
    return SimpleNamespace(
        is_active=active,
        verification_status="verified",
        eligibility_verification_status="verified",
        source_url=source_url,
        source=source,
        eligibility_rules=list(rules),
        state=None, min_age=None, max_age=None, education=None,
        employment_status=None, category=None, max_annual_income=None,
        versions=[],
    )


def test_dynamic_rules_are_case_insensitive_and_explain_success():
    eligible, reasons = check_scheme_eligibility(
        profile(state="karnataka"),
        scheme(rule("state", "equals", "KARNATAKA")),
    )
    assert eligible is True
    assert reasons == ["Rule group 1 matched (AND): state equals KARNATAKA"]


def test_all_failed_groups_are_reported():
    eligible, reasons = check_scheme_eligibility(
        profile(age=16, annual_income=300000),
        scheme(
            rule("age", "gte", "18", group_id=1),
            rule("annual_income", "lte", "250000", group_id=2),
        ),
    )
    assert eligible is False
    assert len(reasons) == 2
    assert "age gte 18" in reasons[0]
    assert "annual_income lte 250000" in reasons[1]


def test_or_group_passes_when_any_rule_matches():
    eligible, _ = check_scheme_eligibility(
        profile(age=21),
        scheme(
            rule("age", "lt", "18", logical_operator="OR"),
            rule("age", "gte", "18", logical_operator="OR"),
        ),
    )
    assert eligible is True


def test_missing_and_malformed_rule_values_fail_closed():
    eligible, reasons = check_scheme_eligibility(
        profile(),
        scheme(
            rule("annual_income", "lte", "250000"),
            rule("age", "gte", "not-a-number", group_id=2),
        ),
    )
    assert eligible is False
    assert "annual_income is missing" in reasons[0]
    assert "Invalid rule value for age" in reasons[1]


def test_inactive_scheme_is_ineligible():
    eligible, reasons = check_scheme_eligibility(profile(), scheme(active=False))
    assert eligible is False
    assert reasons == ["Scheme is currently inactive"]


def test_unverified_rules_and_unregistered_sources_are_never_authoritative():
    candidate = scheme(rule("age", "gte", "18"))
    candidate.verification_status = "pending"
    assert check_scheme_eligibility(profile(), candidate) == (
        False, ["Eligibility is not confirmed from a verified official source"]
    )

    candidate.verification_status = "verified"
    candidate.source = None
    assert check_scheme_eligibility(profile(), candidate) == (
        False, ["Eligibility source is not registered or active"]
    )


def test_verified_scheme_without_recorded_criteria_does_not_default_to_eligible():
    eligible, reasons = check_scheme_eligibility(profile(), scheme())
    assert eligible is False
    assert reasons == ["No verified eligibility criteria are recorded"]


def test_expired_or_not_yet_effective_verified_versions_fail_closed():
    candidate = scheme(rule("age", "gte", "18"))
    candidate.versions = [SimpleNamespace(
        verification_status="verified", version_number=1,
        effective_from=None, effective_until=date.today() - timedelta(days=1),
    )]
    assert check_scheme_eligibility(profile(), candidate) == (
        False, ["The verified scheme version has expired"]
    )
    candidate.versions[0].effective_until = None
    candidate.versions[0].effective_from = date.today() + timedelta(days=1)
    assert check_scheme_eligibility(profile(), candidate) == (
        False, ["The verified scheme version is not yet effective"]
    )


# ==============================================================================
# STAGE 6D REGRESSION & ELIGIBILITY ENGINE CORRECTION TESTS
# ==============================================================================

def test_sc_st_obc_not_compared_against_sector_category():
    """Verify that citizen reservation categories (SC/ST/OBC) are never compared against scheme sectors."""
    categories = ["OBC", "SC", "ST", "General", "EWS"]
    sectors = [
        "Agriculture, Rural & Environment",
        "Education & Learning",
        "Health & Wellness",
        "Housing & Shelter",
        "Banking, Financial Services and Insurance",
    ]

    for cat in categories:
        user = profile(category=cat, state="Karnataka")
        for sector in sectors:
            # Scheme has sector category and state criterion
            candidate = scheme()
            candidate.category = sector
            candidate.state = "Karnataka"

            assessment = check_scheme_eligibility(user, candidate)
            assert assessment.eligible is True
            assert assessment.status == "eligible"
            assert "State matches" in assessment.reasons
            # Critical: category mismatch string must NEVER appear
            assert not any("Category does not match" in r for r in assessment.reasons)
            assert not any(sector in r for r in assessment.reasons)


def test_verified_scheme_explicit_matching_rules_assessed_correctly():
    """Verify that a verified scheme with explicit matching rules evaluates citizen attributes accurately."""
    candidate = scheme(
        rule("is_farmer", "equals", "true"),
        rule("land_ownership", "equals", "true"),
    )
    qualifying_farmer = profile(is_farmer=True, land_ownership=True)
    assessment = check_scheme_eligibility(qualifying_farmer, candidate)

    assert assessment.eligible is True
    assert assessment.status == "eligible"
    assert "Rule group 1 matched (AND): is_farmer equals true, land_ownership equals true" in assessment.reasons[0]

    # Explicit category rule
    category_scheme = scheme(
        rule("category", "in", '["SC", "ST"]'),
    )
    sc_citizen = profile(category="SC")
    assessment_sc = check_scheme_eligibility(sc_citizen, category_scheme)
    assert assessment_sc.eligible is True
    assert assessment_sc.status == "eligible"

    obc_citizen = profile(category="OBC")
    assessment_obc = check_scheme_eligibility(obc_citizen, category_scheme)
    assert assessment_obc.eligible is False
    assert assessment_obc.status == "ineligible"


def test_failed_explicit_rule_produces_ineligible_outcome():
    """Verify that an explicit mismatch on a verified rule produces status='ineligible'."""
    candidate = scheme(
        rule("age", "gte", "18"),
        rule("owns_house", "equals", "false"),
    )
    underage_homeowner = profile(age=16, owns_house=True)
    assessment = check_scheme_eligibility(underage_homeowner, candidate)

    assert assessment.eligible is False
    assert assessment.status == "ineligible"
    assert len(assessment.missing_fields) == 0
    assert "age gte 18" in assessment.reasons[0]
    assert "owns_house equals false" in assessment.reasons[0]


def test_missing_required_profile_information_produces_needs_more_info():
    """Verify that missing profile information on required fields yields status='needs_more_info'."""
    # Dynamic rule with missing income
    candidate_dyn = scheme(
        rule("annual_income", "lte", "250000"),
    )
    user_no_income = profile(annual_income=None)
    assessment_dyn = check_scheme_eligibility(user_no_income, candidate_dyn)

    assert assessment_dyn.eligible is False
    assert assessment_dyn.status == "needs_more_info"
    assert "annual_income" in assessment_dyn.missing_fields
    assert "annual_income is missing" in assessment_dyn.reasons[0]

    # Legacy criteria with missing education
    candidate_leg = scheme()
    candidate_leg.education = "Graduate"
    user_no_edu = profile(education=None)
    assessment_leg = check_scheme_eligibility(user_no_edu, candidate_leg)

    assert assessment_leg.eligible is False
    assert assessment_leg.status == "needs_more_info"
    assert "education" in assessment_leg.missing_fields
    assert "Education information is missing" in assessment_leg.reasons[0]


def test_unverified_schemes_remain_unverified_and_never_eligible():
    """Verify fail-closed behavior: unverified schemes always return status='unverified'."""
    # 1. eligibility_verification_status unverified
    candidate_1 = scheme(rule("age", "gte", "18"))
    candidate_1.eligibility_verification_status = "unverified"
    res1 = check_scheme_eligibility(profile(age=25), candidate_1)
    assert res1.eligible is False
    assert res1.status == "unverified"
    assert res1.reasons == ["Eligibility criteria have not been verified; check the official source"]

    # 2. source verification status unverified
    candidate_2 = scheme(rule("age", "gte", "18"))
    candidate_2.verification_status = "unverified"
    res2 = check_scheme_eligibility(profile(age=25), candidate_2)
    assert res2.eligible is False
    assert res2.status == "unverified"
    assert res2.reasons == ["Eligibility is not confirmed from a verified official source"]

    # 3. No verified criteria recorded
    candidate_3 = scheme()
    res3 = check_scheme_eligibility(profile(age=25), candidate_3)
    assert res3.eligible is False
    assert res3.status == "unverified"
    assert res3.reasons == ["No verified eligibility criteria are recorded"]


def test_scheme_source_mismatches_schemes_9_and_10_remain_safely_blocked():
    """Verify that Schemes 9 and 10 remain blocked as unverified due to remaining source mismatches."""
    with get_live_db_session() as db:
        scheme_9 = db.query(Scheme).filter(Scheme.id == 9).first()
        scheme_10 = db.query(Scheme).filter(Scheme.id == 10).first()

        assert scheme_9 is not None and scheme_9.is_active is True
        res_9 = check_scheme_eligibility(profile(category="OBC"), scheme_9)
        assert res_9.eligible is False
        assert res_9.status == "unverified"
        assert res_9.reasons in (
            ["Eligibility is not confirmed from a verified official source"],
            ["Eligibility source is not registered or active"],
            ["Eligibility criteria have not been verified; check the official source"],
        )

        assert scheme_10 is not None and scheme_10.is_active is True
        res_10 = check_scheme_eligibility(profile(category="OBC"), scheme_10)
        assert res_10.eligible is False
        assert res_10.status == "unverified"
        assert res_10.reasons in (
            ["Eligibility is not confirmed from a verified official source"],
            ["Eligibility source is not registered or active"],
            ["Eligibility criteria have not been verified; check the official source"],
        )


def test_tuple_unpacking_and_response_shape_compatibility():
    """Verify 100% backwards compatibility for tuple unpacking and EligibleSchemeResponse serialization."""
    candidate = scheme(rule("age", "gte", "18"))
    user = profile(age=25)

    assessment = check_scheme_eligibility(user, candidate)

    # 1. Unpacking into 2-tuple
    eligible, reasons = assessment
    assert eligible is True
    assert isinstance(reasons, list)

    # 2. Subscripting and length
    assert assessment[0] is True
    assert assessment[1] == reasons
    assert len(assessment) == 2

    # 3. Equality with 2-tuple (both directions)
    assert assessment == (True, reasons)
    assert (True, reasons) == assessment

    # 4. API Response Schema construction and serialization
    response = EligibleSchemeResponse(
        id=999,
        name="Compatibility Scheme",
        description="Testing schema shape",
        state="Karnataka",
        benefit="Test benefit",
        required_documents=None,
        application_url=None,
        application_deadline=None,
        is_active=True,
        min_age=18,
        max_age=None,
        education=None,
        employment_status=None,
        category="Education & Learning",
        max_annual_income=None,
        eligible=assessment.eligible,
        reasons=assessment.reasons,
        assessment_status=assessment.status,
        missing_fields=assessment.missing_fields,
    )
    serialized = response.model_dump()
    assert serialized["eligible"] is True
    assert serialized["assessment_status"] == "eligible"
    assert serialized["missing_fields"] == []
    assert serialized["reasons"] == reasons


def test_no_runtime_exceptions_across_all_125_active_schemes():
    """Verify that all 125 active schemes in the database can be evaluated without any runtime exceptions."""
    farmer = profile(
        full_name="Kisan Test",
        age=45,
        state="Tamil Nadu",
        category="OBC",
        employment_status="Self-Employed",
        is_farmer=True,
        land_ownership=True,
        annual_income=120000,
    )
    student = profile(
        full_name="Student Test",
        age=20,
        state="Tamil Nadu",
        category="SC",
        is_farmer=False,
        land_ownership=False,
        employment_status="Student",
        annual_income=85000,
    )

    student_missing_info = profile(
        full_name="Student Missing Info",
        age=20,
        gender=None,
        state="Tamil Nadu",
        category="SC",
        is_farmer=False,
        land_ownership=False,
        employment_status="Student",
        annual_income=85000,
    )

    female_student = profile(
        full_name="Kavitha Test",
        age=20,
        gender="Female",
        state="Tamil Nadu",
        category="OBC",
        is_farmer=False,
        land_ownership=False,
        employment_status="Student",
        annual_income=85000,
    )

    verified_scheme_ids = {11, 25, 30, 55, 116}

    with get_live_db_session() as db:
        active_schemes = db.query(Scheme).filter(Scheme.is_active == True).all()
        assert len(active_schemes) == 125, f"Expected 125 active schemes, found {len(active_schemes)}"

        for s in active_schemes:
            # Evaluate for farmer
            res_farmer = check_scheme_eligibility(farmer, s)
            assert isinstance(res_farmer, EligibilityAssessment)

            # Evaluate for student (gender='Other' by default fixture)
            res_student = check_scheme_eligibility(student, s)
            assert isinstance(res_student, EligibilityAssessment)

            # Evaluate for student with missing gender
            res_missing = check_scheme_eligibility(student_missing_info, s)
            assert isinstance(res_missing, EligibilityAssessment)

            # Evaluate for female student (Tamil Nadu resident)
            res_female = check_scheme_eligibility(female_student, s)
            assert isinstance(res_female, EligibilityAssessment)

            if s.id in verified_scheme_ids:
                assert s.eligibility_verification_status == "verified"
                # Farmer outcomes
                if s.id in {11, 25}:
                    assert res_farmer.status == "eligible" and res_farmer.eligible is True
                else:
                    assert res_farmer.status == "ineligible" and res_farmer.eligible is False

                # Student outcomes (gender='Other' fails female-specific schemes explicitly)
                if s.id == 30:
                    assert res_student.status == "eligible" and res_student.eligible is True
                else:
                    assert res_student.status == "ineligible" and res_student.eligible is False

                # Missing info student outcomes (missing gender triggers needs_more_info on female-specific schemes)
                if s.id == 30:
                    assert res_missing.status == "eligible" and res_missing.eligible is True
                elif s.id in {11, 25}:
                    assert res_missing.status == "ineligible" and res_missing.eligible is False
                elif s.id in {55, 116}:
                    assert res_missing.status == "needs_more_info" and "gender" in res_missing.missing_fields

                # Female student outcomes (Pudhumai Penn, CSSS, Pragati match; Agri schemes fail)
                if s.id in {30, 55, 116}:
                    assert res_female.status == "eligible" and res_female.eligible is True
                elif s.id in {11, 25}:
                    assert res_female.status == "ineligible" and res_female.eligible is False
            else:
                # All other 120 schemes MUST fail-closed to unverified
                assert s.eligibility_verification_status == "unverified"
                assert res_farmer.status == "unverified" and res_farmer.eligible is False
                assert res_student.status == "unverified" and res_student.eligible is False
                assert res_missing.status == "unverified" and res_missing.eligible is False
                assert res_female.status == "unverified" and res_female.eligible is False


def test_api_eligibility_matches_returns_all_four_outcomes():
    """Verify that the HTTP endpoint /api/eligibility/matches can return all four assessment outcomes.

    Demonstrates:
    - eligible: Verified scheme with matching rule
    - ineligible: Verified scheme with non-matching rule
    - needs_more_info: Verified scheme with rule requiring field missing from profile
    - unverified: Scheme with unverified eligibility criteria
    """
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    try:
        with SessionLocal() as db:
            user = User(email="all_outcomes@example.com", password_hash=hash_password("test_pass_123"))
            db.add(user)
            db.flush()
            user_id = user.id

            prof = UserProfile(
                user_id=user_id,
                full_name="Comprehensive Test Citizen",
                age=25,
                gender="Other",
                state="Karnataka",
                category="OBC",
                annual_income=None,  # Missing income to trigger needs_more_info
            )
            db.add(prof)

            source = SchemeSource(
                source_name="Official National Portal",
                source_url="https://nationalportal.gov.in/schemes",
                is_active=True,
            )
            db.add(source)
            db.flush()

            # 1. Eligible scheme
            s1 = Scheme(
                name="Verified Adult Citizen Benefit",
                description="Benefit for verified citizens age 18 and older.",
                benefit="Financial support grant.",
                is_active=True,
                source=source,
                source_url=source.source_url,
                verification_status="verified",
                eligibility_verification_status="verified",
            )
            # 2. Ineligible scheme
            s2 = Scheme(
                name="Verified Senior Citizen Pension",
                description="Pension for senior citizens aged 60 and older.",
                benefit="Monthly pension grant.",
                is_active=True,
                source=source,
                source_url=source.source_url,
                verification_status="verified",
                eligibility_verification_status="verified",
            )
            # 3. Needs More Info scheme
            s3 = Scheme(
                name="Verified Income-Assessed Scholarship",
                description="Scholarship requiring verified income threshold.",
                benefit="Tuition assistance.",
                is_active=True,
                source=source,
                source_url=source.source_url,
                verification_status="verified",
                eligibility_verification_status="verified",
            )
            # 4. Unverified scheme
            s4 = Scheme(
                name="Provisional Unverified Initiative",
                description="Initiative awaiting official criteria verification.",
                benefit="General assistance.",
                is_active=True,
                source=source,
                source_url=source.source_url,
                verification_status="unverified",
                eligibility_verification_status="unverified",
            )
            db.add_all([s1, s2, s3, s4])
            db.flush()

            r1 = EligibilityRule(
                scheme_id=s1.id, field_name="age", operator="gte", value="18",
                group_id=1, logical_operator="AND", is_active=True,
            )
            r2 = EligibilityRule(
                scheme_id=s2.id, field_name="age", operator="gte", value="60",
                group_id=1, logical_operator="AND", is_active=True,
            )
            r3 = EligibilityRule(
                scheme_id=s3.id, field_name="annual_income", operator="lte", value="200000",
                group_id=1, logical_operator="AND", is_active=True,
            )
            db.add_all([r1, r2, r3])
            db.commit()

        token = create_access_token(user_id=user_id)
        with TestClient(app) as client:
            res = client.get("/api/eligibility/matches", headers={"Authorization": f"Bearer {token}"})
            assert res.status_code == 200
            data = res.json()

        outcome_by_name = {item["name"]: item for item in data}

        # 1. Validate 'eligible'
        eligible_item = outcome_by_name["Verified Adult Citizen Benefit"]
        assert eligible_item["eligible"] is True
        assert eligible_item["assessment_status"] == "eligible"
        assert eligible_item["missing_fields"] == []
        assert any("age gte 18" in reason for reason in eligible_item["reasons"])

        # 2. Validate 'ineligible'
        ineligible_item = outcome_by_name["Verified Senior Citizen Pension"]
        assert ineligible_item["eligible"] is False
        assert ineligible_item["assessment_status"] == "ineligible"
        assert ineligible_item["missing_fields"] == []
        assert any("age gte 60" in reason for reason in ineligible_item["reasons"])

        # 3. Validate 'needs_more_info'
        nmi_item = outcome_by_name["Verified Income-Assessed Scholarship"]
        assert nmi_item["eligible"] is False
        assert nmi_item["assessment_status"] == "needs_more_info"
        assert nmi_item["missing_fields"] == ["annual_income"]
        assert any("annual_income is missing" in reason for reason in nmi_item["reasons"])

        # 4. Validate 'unverified'
        unverified_item = outcome_by_name["Provisional Unverified Initiative"]
        assert unverified_item["eligible"] is False
        assert unverified_item["assessment_status"] == "unverified"
        assert unverified_item["missing_fields"] == []

        distinct_statuses = {item["assessment_status"] for item in data}
        assert distinct_statuses == {"eligible", "ineligible", "needs_more_info", "unverified"}
    finally:
        Base.metadata.drop_all(bind=engine)
