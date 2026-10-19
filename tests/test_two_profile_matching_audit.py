from types import SimpleNamespace
from datetime import date, timedelta
import pytest

from app.database.connection import SessionLocal
from app.models.scheme import Scheme
from app.models.profile import UserProfile
from app.models.eligibility_rule import EligibilityRule
from app.services.eligibility import check_scheme_eligibility, _check_dynamic_rules


def make_farmer_profile(**overrides):
    attrs = dict(
        full_name="Synthetic Farmer Thiru Murugan",
        age=45,
        gender="Male",
        marital_status="Married",
        state="Tamil Nadu",
        district="Thanjavur",
        domicile_state="Tamil Nadu",
        rural_or_urban="rural",
        category="OBC",
        minority_status=False,
        education="Secondary",
        employment_status="Self-Employed",
        occupation="farmer",
        beneficiary_group="Farmer",
        fisher_activity=None,
        annual_income=120000,
        income_source="Agriculture",
        income_certificate_available=True,
        bpl_status=False,
        ration_card_type="PHH",
        family_size=4,
        dependents=2,
        parents_alive=True,
        single_parent=False,
        orphan=False,
        has_disability=False,
        disability_type=None,
        disability_percentage=None,
        disability_certificate_available=False,
        is_farmer=True,
        land_ownership=True,
        land_area=2.5,
        land_unit="acre",
        crop_type="Paddy",
        irrigation_available=True,
        owns_house=True,
        house_type="Semi-Pucca",
        housing_condition="Fair",
        electricity_available=True,
        toilet_available=True,
        widow=False,
        ex_serviceman_family=False,
        senior_citizen=False,
    )
    attrs.update(overrides)
    return UserProfile(**attrs)


def make_student_profile(**overrides):
    attrs = dict(
        full_name="Synthetic Student Selvi Kavitha",
        age=20,
        gender="Female",
        marital_status="Single",
        state="Tamil Nadu",
        district="Coimbatore",
        domicile_state="Tamil Nadu",
        rural_or_urban="urban",
        category="SC",
        minority_status=False,
        education="Higher Secondary",
        course="B.Sc Computer Science",
        specialization="Computer Science",
        institution_type="Government College",
        year_of_study=2,
        previous_qualification="Higher Secondary (12th)",
        marks_percentage=84.5,
        employment_status="Student",
        occupation="Student",
        beneficiary_group="Student",
        fisher_activity=None,
        annual_income=85000,
        income_source="Daily Wage",
        income_certificate_available=True,
        bpl_status=True,
        ration_card_type="BPL / PHH",
        family_size=4,
        dependents=2,
        parents_alive=True,
        single_parent=False,
        orphan=False,
        has_disability=False,
        disability_type=None,
        disability_percentage=None,
        disability_certificate_available=False,
        is_farmer=False,
        land_ownership=False,
        land_area=None,
        land_unit=None,
        crop_type=None,
        irrigation_available=False,
        owns_house=False,
        house_type="Rented",
        housing_condition="Fair",
        electricity_available=True,
        toilet_available=True,
        widow=False,
        ex_serviceman_family=False,
        senior_citizen=False,
    )
    attrs.update(overrides)
    return UserProfile(**attrs)


def make_mock_scheme(*rules, **overrides):
    source_url = "https://official.gov.in/scheme"
    source = SimpleNamespace(is_active=True, source_url=source_url)
    defaults = dict(
        id=999,
        name="Mock Scheme",
        is_active=True,
        verification_status="verified",
        eligibility_verification_status="verified",
        source_url=source_url,
        source=source,
        eligibility_rules=list(rules),
        state=None,
        min_age=None,
        max_age=None,
        education=None,
        employment_status=None,
        category=None,
        max_annual_income=None,
        versions=[],
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_different_profiles_produce_appropriately_different_results():
    """Verify that distinct profiles produce distinct and correct matching results."""
    farmer = make_farmer_profile()
    student = make_student_profile()

    pm_kisan_rules = [
        EligibilityRule(field_name="is_farmer", operator="equals", value="true"),
        EligibilityRule(field_name="land_ownership", operator="equals", value="true"),
    ]
    pm_kisan_scheme = make_mock_scheme(*pm_kisan_rules, name="PM-KISAN")

    # Farmer matches PM-KISAN
    farmer_ok, farmer_reasons = check_scheme_eligibility(farmer, pm_kisan_scheme)
    assert farmer_ok is True
    assert "is_farmer equals true" in farmer_reasons[0]
    assert "land_ownership equals true" in farmer_reasons[0]

    # Student fails PM-KISAN
    student_ok, student_reasons = check_scheme_eligibility(student, pm_kisan_scheme)
    assert student_ok is False
    assert "is_farmer equals true" in student_reasons[0]
    assert "land_ownership equals true" in student_reasons[0]

    # Housing scheme: PMAY-U 2.0 (urban, owns_house == False, income <= 9L)
    pmay_u_rules = [
        EligibilityRule(field_name="rural_or_urban", operator="equals", value="urban"),
        EligibilityRule(field_name="owns_house", operator="equals", value="false"),
        EligibilityRule(field_name="annual_income", operator="lte", value="900000"),
    ]
    pmay_scheme = make_mock_scheme(*pmay_u_rules, name="PMAY-U 2.0")

    # Student matches PMAY-U
    s_ok, s_reasons = check_scheme_eligibility(student, pmay_scheme)
    assert s_ok is True
    assert "rural_or_urban equals urban" in s_reasons[0]
    assert "owns_house equals false" in s_reasons[0]

    # Rural farmer fails PMAY-U
    f_ok, f_reasons = check_scheme_eligibility(farmer, pmay_scheme)
    assert f_ok is False
    assert "rural_or_urban equals urban" in f_reasons[0]
    assert "owns_house equals false" in f_reasons[0]


def test_missing_profile_fields_fail_closed_with_explicit_reason():
    """Missing or unspecified profile attributes must not be silently treated as matching."""
    profile_with_missing_land = make_farmer_profile(land_ownership=None)
    pm_kisan_rules = [
        EligibilityRule(field_name="is_farmer", operator="equals", value="true"),
        EligibilityRule(field_name="land_ownership", operator="equals", value="true"),
    ]
    scheme = make_mock_scheme(*pm_kisan_rules)
    ok, reasons = check_scheme_eligibility(profile_with_missing_land, scheme)
    assert ok is False
    assert "land_ownership is missing" in reasons[0]

    profile_missing_income = make_student_profile(annual_income=None)
    income_rule = [EligibilityRule(field_name="annual_income", operator="lte", value="250000")]
    scheme_income = make_mock_scheme(*income_rule)
    ok_inc, reasons_inc = check_scheme_eligibility(profile_missing_income, scheme_income)
    assert ok_inc is False
    assert "annual_income is missing" in reasons_inc[0]


def test_unverified_scheme_status_never_produces_guaranteed_eligibility():
    """When eligibility_verification_status is 'unverified', engine must never claim eligibility."""
    farmer = make_farmer_profile()
    scheme = make_mock_scheme(
        EligibilityRule(field_name="is_farmer", operator="equals", value="true"),
        eligibility_verification_status="unverified",
    )
    ok, reasons = check_scheme_eligibility(farmer, scheme)
    assert ok is False
    assert reasons == ["Eligibility criteria have not been verified; check the official source"]

    # When source is unverified
    scheme.eligibility_verification_status = "verified"
    scheme.verification_status = "unverified"
    ok, reasons = check_scheme_eligibility(farmer, scheme)
    assert ok is False
    assert reasons == ["Eligibility is not confirmed from a verified official source"]

    # When source is unregistered
    scheme.verification_status = "verified"
    scheme.source = None
    ok, reasons = check_scheme_eligibility(farmer, scheme)
    assert ok is False
    assert reasons == ["Eligibility source is not registered or active"]


def test_inactive_duplicate_schemes_and_canonical_targets_handling():
    """Verify handling of inactive duplicate schemes and canonical targets."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.database.base import Base

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        canonical_pm_kisan = Scheme(
            id=11,
            name="Pradhan Mantri Kisan Samman Nidhi (PM-KISAN)",
            slug="pm-kisan",
            description="Direct benefit transfer to landholding farmers",
            benefit="Rs 6000 per year",
            is_active=True,
            verification_status="verified",
            eligibility_verification_status="verified",
            source_url="https://pmkisan.gov.in/",
        )
        archived_pm_kisan = Scheme(
            id=6,
            name="PM-KISAN Samman Nidhi [Archived Duplicate of #11]",
            slug="pm-kisan-archived-6",
            description="Archived duplicate record",
            benefit="Archived",
            is_active=False,
            canonical_scheme_id=11,
            source_url="https://pmkisan.gov.in/",
        )
        db.add_all([canonical_pm_kisan, archived_pm_kisan])
        db.commit()

        # Active schemes query must exclude inactive duplicate
        active_schemes = db.query(Scheme).filter(Scheme.is_active == True).all()
        active_ids = {s.id for s in active_schemes}
        assert 11 in active_ids
        assert 6 not in active_ids

        # Duplicate must reference canonical target
        dup = db.query(Scheme).filter(Scheme.id == 6).first()
        assert dup.is_active is False
        assert dup.canonical_scheme_id == 11
        assert dup.canonical_scheme.name == "Pradhan Mantri Kisan Samman Nidhi (PM-KISAN)"


def test_category_semantic_distinction_documented():
    """Demonstrates that UserProfile.category (social reservation) is no longer compared with Scheme.category (sector)."""
    farmer = make_farmer_profile()  # category='OBC'

    # 1. Scheme with sector category 'Agriculture' and NO criteria recorded
    scheme_no_criteria = make_mock_scheme(
        category="Agriculture",
        eligibility_rules=[],
    )
    assessment_no_crit = check_scheme_eligibility(farmer, scheme_no_criteria)
    # The scheme sector is not treated as a criterion; no criteria are recorded
    assert assessment_no_crit.eligible is False
    assert assessment_no_crit.status == "unverified"
    assert assessment_no_crit.reasons == ["No verified eligibility criteria are recorded"]
    assert "Category does not match" not in str(assessment_no_crit.reasons)

    # 2. Scheme with state criteria and sector 'Agriculture'
    scheme_with_state = make_mock_scheme(
        state="Tamil Nadu",
        category="Agriculture",
        eligibility_rules=[],
    )
    assessment_state = check_scheme_eligibility(farmer, scheme_with_state)
    # Citizen is OBC, scheme sector is Agriculture; citizen is NOT rejected on category
    assert assessment_state.eligible is True
    assert assessment_state.status == "eligible"
    assert "State matches" in assessment_state.reasons
    assert "Category does not match" not in str(assessment_state.reasons)
