"""Regression tests for Stage 3 data corrections and rollback mechanism.

Verifies:
1. Exact preservation and restoration of Scheme 37 category ('Business & Entrepreneurship') on Python rollback.
2. Full round-trip fidelity of all 20 records (schemes, eligibility rules, documents, sources) via Python execute_rollback_from_snapshot.
3. Full round-trip fidelity of all 20 records via raw SQL rollback script (stage3_corrections_rollback.sql).
4. Eligibility engine behavior when rules are attached but eligibility_verification_status is 'unverified' (fails closed).
5. Eligibility engine behavior when eligibility_verification_status is 'verified' (matches dynamic rules).
6. Eligibility engine behavior for deactivated/archived duplicate schemes (ineligible).
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest
from sqlalchemy import create_engine, text

# Add backend/scripts to sys.path so execute_rollback_from_snapshot can be imported
SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "backend" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from stage3_data_corrections import execute_rollback_from_snapshot
from app.models.eligibility_rule import EligibilityRule
from app.models.profile import UserProfile
from app.services.eligibility import check_scheme_eligibility


@pytest.fixture
def isolated_db():
    """Create an isolated in-memory SQLite database populated with pre-correction records."""
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE schemes (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT,
                state TEXT,
                source_url TEXT,
                is_active BOOLEAN NOT NULL,
                verification_status TEXT,
                eligibility_verification_status TEXT DEFAULT 'unverified'
            );
        """))
        conn.execute(text("""
            CREATE TABLE eligibility_rules (
                id INTEGER PRIMARY KEY,
                scheme_id INTEGER NOT NULL,
                field_name TEXT NOT NULL,
                operator TEXT NOT NULL,
                value TEXT NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT 1
            );
        """))
        conn.execute(text("""
            CREATE TABLE scheme_documents (
                id INTEGER PRIMARY KEY,
                scheme_id INTEGER NOT NULL,
                source_url TEXT NOT NULL
            );
        """))
        conn.execute(text("""
            CREATE TABLE scheme_sources (
                id INTEGER PRIMARY KEY,
                source_name TEXT NOT NULL,
                source_url TEXT NOT NULL
            );
        """))

        # Seed exact pre-correction state matching live database
        conn.execute(text("""
            INSERT INTO schemes (id, name, category, state, source_url, is_active, verification_status, eligibility_verification_status) VALUES
            (6, 'PM-KISAN Samman Nidhi', NULL, NULL, NULL, 1, NULL, 'unverified'),
            (11, 'Pradhan Mantri Kisan Samman Nidhi (PM-KISAN)', 'Agriculture', NULL, 'https://pmkisan.gov.in/', 1, 'verified', 'unverified'),
            (8, 'Pradhan Mantri Awas Yojana - Urban 2.0 (PMAY-U 2.0)', NULL, NULL, NULL, 1, NULL, 'unverified'),
            (19, 'Pradhan Mantri Awas Yojana — Urban 2.0 (PMAY-U 2.0)', 'Housing', NULL, 'https://pmay-urban.gov.in/', 1, 'verified', 'unverified'),
            (37, 'Pradhan Mantri Formalisation of Micro Food Processing Enterprises Scheme (PMFME)', 'Business & Entrepreneurship', NULL, 'https://pmfme.mofpi.gov.in/pmfme/', 1, 'pending', 'unverified'),
            (88, 'Pradhan Mantri Formalisation of Micro Food Processing Enterprises (PMFME)', 'Business & Entrepreneurship', NULL, 'https://pmfme.mofpi.gov.in/', 1, 'verified', 'unverified'),
            (116, 'Moovalur Ramamirtham Ammaiyar Higher Education Assurance Scheme (Pudhumai Penn)', 'Education', 'Tamil Nadu', 'https://pudhumaimaipen.tn.gov.in/', 1, 'verified', 'unverified'),
            (76, 'Deendayal Antyodaya Yojana - National Rural Livelihoods Mission (DAY-NRLM)', 'Housing', NULL, 'https://nrlm.gov.in/', 1, 'verified', 'unverified'),
            (77, 'Swachh Bharat Mission (Grameen) — Individual Household Latrine (IHHL)', 'Housing', NULL, 'https://sbm.gov.in/sbmgramin/', 1, 'verified', 'unverified');
        """))

        conn.execute(text("""
            INSERT INTO eligibility_rules (id, scheme_id, field_name, operator, value, is_active) VALUES
            (8, 6, 'is_farmer', 'equals', 'true', 1),
            (9, 6, 'land_ownership', 'equals', 'true', 1),
            (12, 8, 'rural_or_urban', 'equals', 'urban', 1),
            (13, 8, 'owns_house', 'equals', 'false', 1),
            (14, 8, 'annual_income', 'lte', '900000', 1);
        """))

        conn.execute(text("""
            INSERT INTO scheme_documents (id, scheme_id, source_url) VALUES
            (107, 116, 'https://pudhumaimaipen.tn.gov.in/'),
            (58, 76, 'https://nrlm.gov.in/'),
            (59, 77, 'https://sbm.gov.in/sbmgramin/');
        """))

        conn.execute(text("""
            INSERT INTO scheme_sources (id, source_name, source_url) VALUES
            (128, 'Government of Tamil Nadu — Pudhumai Penn Portal', 'https://pudhumaimaipen.tn.gov.in/'),
            (79, 'National Rural Livelihoods Mission Portal', 'https://nrlm.gov.in/'),
            (80, 'Swachh Bharat Mission — Grameen Portal', 'https://sbm.gov.in/sbmgramin/');
        """))

    return engine


def _capture_db_state(conn):
    """Helper to capture full state of all 20 target records."""
    return {
        "schemes": {
            row.id: dict(row._mapping) for row in conn.execute(text("SELECT id, name, is_active, category, source_url, verification_status FROM schemes ORDER BY id")).fetchall()
        },
        "rules": {
            row.id: dict(row._mapping) for row in conn.execute(text("SELECT id, scheme_id, field_name, value FROM eligibility_rules ORDER BY id")).fetchall()
        },
        "docs": {
            row.id: dict(row._mapping) for row in conn.execute(text("SELECT id, scheme_id, source_url FROM scheme_documents ORDER BY id")).fetchall()
        },
        "sources": {
            row.id: dict(row._mapping) for row in conn.execute(text("SELECT id, source_name, source_url FROM scheme_sources ORDER BY id")).fetchall()
        }
    }


def test_python_rollback_from_manifest_roundtrip(isolated_db):
    """Test that applying forward corrections and then Python execute_rollback_from_snapshot restores all original values exactly."""
    # 1. Capture exact snapshot before forward migration
    with isolated_db.connect() as conn:
        pre_snapshot = _capture_db_state(conn)

    # Verify Scheme 37 pre-condition category is 'Business & Entrepreneurship'
    assert pre_snapshot["schemes"][37]["category"] == "Business & Entrepreneurship"
    assert pre_snapshot["schemes"][37]["is_active"] == 1
    assert pre_snapshot["schemes"][76]["category"] == "Housing"
    assert pre_snapshot["schemes"][77]["category"] == "Housing"

    # 2. Execute forward migration
    with isolated_db.begin() as conn:
        conn.execute(text("UPDATE eligibility_rules SET scheme_id = 11 WHERE id IN (8, 9)"))
        conn.execute(text("UPDATE schemes SET is_active = 0, name = 'PM-KISAN Samman Nidhi [Archived Duplicate of #11]' WHERE id = 6"))

        conn.execute(text("UPDATE eligibility_rules SET scheme_id = 19 WHERE id IN (12, 13, 14)"))
        conn.execute(text("UPDATE schemes SET is_active = 0, name = 'Pradhan Mantri Awas Yojana - Urban 2.0 (PMAY-U 2.0) [Archived Duplicate of #19]' WHERE id = 8"))

        conn.execute(text("UPDATE schemes SET is_active = 0, name = 'Pradhan Mantri Formalisation of Micro Food Processing Enterprises Scheme (PMFME) [Archived Duplicate of #88]' WHERE id = 37"))

        conn.execute(text("UPDATE schemes SET source_url = 'https://pudhumaipenn.tn.gov.in/' WHERE id = 116"))
        conn.execute(text("UPDATE scheme_documents SET source_url = 'https://pudhumaipenn.tn.gov.in/' WHERE id = 107"))
        conn.execute(text("UPDATE scheme_sources SET source_url = 'https://pudhumaipenn.tn.gov.in/' WHERE id = 128"))

        conn.execute(text("UPDATE schemes SET source_url = 'https://aajeevika.gov.in/', category = 'Employment & Skills' WHERE id = 76"))
        conn.execute(text("UPDATE scheme_documents SET source_url = 'https://aajeevika.gov.in/' WHERE id = 58"))
        conn.execute(text("UPDATE scheme_sources SET source_url = 'https://aajeevika.gov.in/' WHERE id = 79"))

        conn.execute(text("UPDATE schemes SET source_url = 'https://swachhbharatmission.ddws.gov.in/', category = 'Health & Wellness' WHERE id = 77"))
        conn.execute(text("UPDATE scheme_documents SET source_url = 'https://swachhbharatmission.ddws.gov.in/' WHERE id = 59"))
        conn.execute(text("UPDATE scheme_sources SET source_url = 'https://swachhbharatmission.ddws.gov.in/' WHERE id = 80"))

    # Verify forward state changed
    with isolated_db.connect() as conn:
        fwd_state = _capture_db_state(conn)
        assert fwd_state["schemes"][37]["is_active"] == 0
        assert fwd_state["schemes"][37]["category"] == "Business & Entrepreneurship"
        assert fwd_state["schemes"][76]["category"] == "Employment & Skills"
        assert fwd_state["schemes"][76]["source_url"] == "https://aajeevika.gov.in/"
        assert fwd_state["rules"][8]["scheme_id"] == 11
        assert fwd_state["rules"][12]["scheme_id"] == 19

    # 3. Load the actual saved rollback manifest JSON
    manifest_path = Path(__file__).resolve().parents[1] / "backups" / "stage3_corrections_rollback_manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)

    # 4. Execute the Python rollback logic directly
    with isolated_db.begin() as conn:
        execute_rollback_from_snapshot(conn, manifest_data)

    # 5. Verify that ALL records match pre-correction state 100% exactly
    with isolated_db.connect() as conn:
        post_state = _capture_db_state(conn)

    # CRITICAL REGRESSION PROOF: Scheme 37 category was PRESERVED, NOT overwritten with NULL!
    assert post_state["schemes"][37]["category"] == "Business & Entrepreneurship"
    assert post_state["schemes"][37]["is_active"] == 1
    assert post_state["schemes"][37]["name"] == "Pradhan Mantri Formalisation of Micro Food Processing Enterprises Scheme (PMFME)"

    # Categories for Schemes 76 & 77 restored to 'Housing'
    assert post_state["schemes"][76]["category"] == "Housing"
    assert post_state["schemes"][76]["source_url"] == "https://nrlm.gov.in/"
    assert post_state["schemes"][77]["category"] == "Housing"
    assert post_state["schemes"][77]["source_url"] == "https://sbm.gov.in/sbmgramin/"

    # Scheme 6 & 8 names and active statuses restored
    assert post_state["schemes"][6]["is_active"] == 1
    assert post_state["schemes"][6]["name"] == "PM-KISAN Samman Nidhi"
    assert post_state["schemes"][8]["is_active"] == 1
    assert post_state["schemes"][8]["name"] == "Pradhan Mantri Awas Yojana - Urban 2.0 (PMAY-U 2.0)"

    # Rule associations restored
    assert post_state["rules"][8]["scheme_id"] == 6
    assert post_state["rules"][9]["scheme_id"] == 6
    assert post_state["rules"][12]["scheme_id"] == 8
    assert post_state["rules"][13]["scheme_id"] == 8
    assert post_state["rules"][14]["scheme_id"] == 8

    # Canonical schemes (11, 19, 88) were NEVER touched or corrupted
    assert post_state["schemes"][11]["category"] == "Agriculture"
    assert post_state["schemes"][11]["source_url"] == "https://pmkisan.gov.in/"
    assert post_state["schemes"][19]["category"] == "Housing"
    assert post_state["schemes"][19]["source_url"] == "https://pmay-urban.gov.in/"
    assert post_state["schemes"][88]["category"] == "Business & Entrepreneurship"

    # Full dictionary equality across all 20 records
    assert post_state["schemes"] == pre_snapshot["schemes"]
    assert post_state["rules"] == pre_snapshot["rules"]
    assert post_state["docs"] == pre_snapshot["docs"]
    assert post_state["sources"] == pre_snapshot["sources"]


def _clean_sql_statements(sql_text: str) -> list[str]:
    """Helper to strip comments and extract executable SQL statements."""
    lines = [line for line in sql_text.splitlines() if not line.strip().startswith("--")]
    cleaned_sql = "\n".join(lines)
    statements = []
    for stmt in cleaned_sql.split(";"):
        s = stmt.strip()
        if s and s not in ("BEGIN", "COMMIT"):
            statements.append(s)
    return statements


def test_sql_rollback_script_roundtrip(isolated_db):
    """Test that executing the raw SQL rollback script restores all records to pre-correction state 100% exactly."""
    with isolated_db.connect() as conn:
        pre_snapshot = _capture_db_state(conn)

    # 1. Apply forward SQL
    forward_sql_path = Path(__file__).resolve().parents[1] / "backups" / "stage3_corrections_forward.sql"
    with open(forward_sql_path, "r", encoding="utf-8") as f:
        forward_sql = f.read()

    with isolated_db.begin() as conn:
        for stmt in _clean_sql_statements(forward_sql):
            conn.execute(text(stmt))

    # 2. Apply rollback SQL
    rollback_sql_path = Path(__file__).resolve().parents[1] / "backups" / "stage3_corrections_rollback.sql"
    with open(rollback_sql_path, "r", encoding="utf-8") as f:
        rollback_sql = f.read()

    with isolated_db.begin() as conn:
        for stmt in _clean_sql_statements(rollback_sql):
            conn.execute(text(stmt))

    # 3. Assert all 20 records match pre-correction state 100%
    with isolated_db.connect() as conn:
        post_sql_state = _capture_db_state(conn)

    assert post_sql_state["schemes"][37]["category"] == "Business & Entrepreneurship"
    assert post_sql_state["schemes"] == pre_snapshot["schemes"]
    assert post_sql_state["rules"] == pre_snapshot["rules"]
    assert post_sql_state["docs"] == pre_snapshot["docs"]
    assert post_sql_state["sources"] == pre_snapshot["sources"]


def test_eligibility_engine_unverified_status_fails_closed():
    """Verify that when a scheme has valid rules but eligibility_verification_status is 'unverified', it fails closed."""
    source_url = "https://pmkisan.gov.in/"
    scheme = SimpleNamespace(
        is_active=True,
        verification_status="verified",
        eligibility_verification_status="unverified",  # Unverified safeguard active
        source_url=source_url,
        source=SimpleNamespace(is_active=True, source_url=source_url),
        eligibility_rules=[
            EligibilityRule(field_name="is_farmer", operator="equals", value="true"),
            EligibilityRule(field_name="land_ownership", operator="equals", value="true"),
        ],
        state=None, min_age=None, max_age=None, education=None,
        employment_status=None, category=None, max_annual_income=None,
        versions=[],
    )

    farmer_profile = UserProfile(
        full_name="Kisan Citizen",
        age=45,
        state="Uttar Pradesh",
        is_farmer=True,
        land_ownership=True,
    )

    eligible, reasons = check_scheme_eligibility(farmer_profile, scheme)
    # MUST fail closed because eligibility_verification_status is 'unverified'
    assert eligible is False
    assert reasons == ["Eligibility criteria have not been verified; check the official source"]


def test_eligibility_engine_verified_status_matches_rules():
    """Verify that when eligibility_verification_status is verified by an administrator, matching profile succeeds."""
    source_url = "https://pmkisan.gov.in/"
    scheme = SimpleNamespace(
        is_active=True,
        verification_status="verified",
        eligibility_verification_status="verified",  # Formally verified by administrator
        source_url=source_url,
        source=SimpleNamespace(is_active=True, source_url=source_url),
        eligibility_rules=[
            EligibilityRule(field_name="is_farmer", operator="equals", value="true"),
            EligibilityRule(field_name="land_ownership", operator="equals", value="true"),
        ],
        state=None, min_age=None, max_age=None, education=None,
        employment_status=None, category=None, max_annual_income=None,
        versions=[],
    )

    farmer_profile = UserProfile(
        full_name="Kisan Citizen",
        age=45,
        state="Uttar Pradesh",
        is_farmer=True,
        land_ownership=True,
    )

    non_farmer_profile = UserProfile(
        full_name="City Resident",
        age=30,
        state="Delhi",
        is_farmer=False,
        land_ownership=False,
    )

    eligible_farmer, reasons_farmer = check_scheme_eligibility(farmer_profile, scheme)
    assert eligible_farmer is True
    assert "Rules matched (AND): is_farmer equals true, land_ownership equals true" in reasons_farmer[0]

    eligible_non_farmer, reasons_non_farmer = check_scheme_eligibility(non_farmer_profile, scheme)
    assert eligible_non_farmer is False
    assert "is_farmer equals true" in reasons_non_farmer[0]


def test_eligibility_engine_inactive_archived_scheme_ineligible():
    """Verify that deactivated duplicate schemes (is_active=False) immediately return ineligible."""
    scheme = SimpleNamespace(
        is_active=False,
        name="PM-KISAN Samman Nidhi [Archived Duplicate of #11]",
        verification_status="verified",
        eligibility_verification_status="verified",
        source_url=None,
        source=None,
        eligibility_rules=[],
        state=None, min_age=None, max_age=None, education=None,
        employment_status=None, category=None, max_annual_income=None,
        versions=[],
    )

    farmer_profile = UserProfile(
        full_name="Kisan Citizen",
        age=45,
        state="Uttar Pradesh",
        is_farmer=True,
        land_ownership=True,
    )

    eligible, reasons = check_scheme_eligibility(farmer_profile, scheme)
    assert eligible is False
    assert reasons == ["Scheme is currently inactive"]
