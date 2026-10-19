"""Unit and isolated integration tests for run_production_migration.py.

Tests strictly negative mocked cases and isolated test database scenarios.
Never connects to or interacts with the production database.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scripts.run_production_migration import (
    TargetIdentityError,
    PreflightValidationError,
    mask_db_url,
    verify_target_identity,
    execute_preflight_checks,
    prompt_operator_confirmation,
    run_production_migration,
)

ISOLATED_TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://test_runner:test_isolation_pw_2026@localhost:5433/lifenavigator_stage3c_test"
)


# ==============================================================================
# 1. Credential Masking Tests
# ==============================================================================
def test_mask_db_url_standard():
    raw_url = "postgresql://myuser:super_secret_password123@localhost:5432/mydb"
    masked = mask_db_url(raw_url)
    assert "super_secret_password123" not in masked
    assert "myuser:****@localhost:5432/mydb" in masked


def test_mask_db_url_with_special_characters():
    raw_url = "postgresql+psycopg://user:p%40ss%3Aword!@db.internal:5432/production_db"
    masked = mask_db_url(raw_url)
    assert "p%40ss%3Aword!" not in masked
    assert "****" in masked


# ==============================================================================
# 2. Mocked Target Identity Assertion Tests (Negative Cases)
# ==============================================================================
def test_verify_target_identity_db_name_mismatch():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = ("wrong_database", "lifenavigator", 5432, "127.0.0.1", "PostgreSQL 16.2")
    mock_conn.cursor.return_value = mock_cur

    with pytest.raises(TargetIdentityError, match="does not match expected database"):
        verify_target_identity(mock_conn, expected_db="lifenavigator", expected_user="lifenavigator")


def test_verify_target_identity_user_mismatch():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = ("lifenavigator", "unauthorized_user", 5432, "127.0.0.1", "PostgreSQL 16.2")
    mock_conn.cursor.return_value = mock_cur

    with pytest.raises(TargetIdentityError, match="does not match expected user"):
        verify_target_identity(mock_conn, expected_db="lifenavigator", expected_user="lifenavigator")


def test_verify_target_identity_port_mismatch():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = ("lifenavigator", "lifenavigator", 5434, "127.0.0.1", "PostgreSQL 16.2")
    mock_conn.cursor.return_value = mock_cur

    with pytest.raises(TargetIdentityError, match="does not match expected port"):
        verify_target_identity(mock_conn, expected_db="lifenavigator", expected_user="lifenavigator", expected_port=5432)


# ==============================================================================
# 3. Mocked Preflight Checks (Negative Cases)
# ==============================================================================
def test_preflight_checks_revision_mismatch_for_upgrade():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    # Mock current revision as wrong parent
    mock_cur.fetchone.return_value = ("wrong_parent_hash",)
    mock_conn.cursor.return_value = mock_cur

    with pytest.raises(PreflightValidationError, match="requires parent 'e1a89b72c431'"):
        execute_preflight_checks(mock_conn, action="upgrade", target_revision="3c1a2b3c4d5e")


def test_preflight_checks_scheme_count_mismatch():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    # 1. revision matches
    # 2. scheme count returns 129 instead of 130
    mock_cur.fetchone.side_effect = [
        ("e1a89b72c431",),
        (129, 124, 5),
    ]
    mock_conn.cursor.return_value = mock_cur

    with pytest.raises(PreflightValidationError, match="Expected 130 total schemes, found 129"):
        execute_preflight_checks(mock_conn, action="upgrade", target_revision="3c1a2b3c4d5e")


# ==============================================================================
# 4. Confirmation Token Validation Tests
# ==============================================================================
def test_prompt_operator_confirmation_valid_token():
    # Should not raise
    prompt_operator_confirmation("upgrade", "3c1a2b3c4d5e", confirmation_token="YES-MIGRATE-PRODUCTION")
    prompt_operator_confirmation("downgrade", "-1", confirmation_token="YES-DOWNGRADE-PRODUCTION")


def test_prompt_operator_confirmation_invalid_token():
    with pytest.raises(ValueError, match="does not match required"):
        prompt_operator_confirmation("upgrade", "3c1a2b3c4d5e", confirmation_token="NO")


def test_prompt_operator_confirmation_interactive_abort():
    with patch("builtins.input", return_value="NO"):
        with pytest.raises(SystemExit):
            prompt_operator_confirmation("upgrade", "3c1a2b3c4d5e", confirmation_token=None)


# ==============================================================================
# 5. Environment Enforcement
# ==============================================================================
def test_run_production_migration_rejects_non_production_env():
    with pytest.raises(SystemExit):
        run_production_migration(
            action="upgrade",
            revision="3c1a2b3c4d5e",
            db_url="postgresql://localhost:5432/db",
            environment="staging"
        )


# ==============================================================================
# 6. Isolated Test Database Preflight Verification
# ==============================================================================
def test_preflight_against_isolated_test_db():
    """Verify preflight read-only checks run cleanly against lifenavigator_stage3c_test."""
    import psycopg2
    try:
        conn = psycopg2.connect(ISOLATED_TEST_DB_URL)
    except Exception:
        pytest.skip("Isolated test database container not reachable.")

    try:
        # Check target identity with test DB expectations (PostgreSQL server listens on 5432 internally)
        identity = verify_target_identity(
            conn,
            expected_db="lifenavigator_stage3c_test",
            expected_user="test_runner",
            expected_port=5432,
        )
        assert identity["database"] == "lifenavigator_stage3c_test"
        assert identity["user"] == "test_runner"

        # Check preflight for downgrade (since test DB is currently at 3c1a2b3c4d5e)
        execute_preflight_checks(conn, action="downgrade", target_revision="-1")
    finally:
        conn.close()
