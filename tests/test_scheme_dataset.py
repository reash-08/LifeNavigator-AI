import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database.base import Base
from app.models.eligibility_rule import EligibilityRule
from app.models.scheme import Scheme
from scripts.seed_schemes import DATASET_PATH, import_records, load_dataset
from app.models.scheme_source import SchemeImportHistory, SchemeSource, SchemeVersion
from app.services.scheme_sync import sync_records


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_starter_dataset_validates_and_covers_agreed_categories():
    dataset = load_dataset(DATASET_PATH)
    categories = {item.category for item in dataset.schemes}
    assert {
        "Agriculture", "Fisheries", "Education", "Women & Child",
        "Senior Citizens", "Disability", "Health", "Housing",
        "Employment & Skills", "Business & Entrepreneurship", "Social Welfare",
    } <= categories
    assert all(item.source_url.startswith("https://") for item in dataset.schemes)
    assert sum(item.verification_status == "verified" and item.verified_at is not None for item in dataset.schemes) >= 100
    assert sum(item.verification_status == "pending" and item.verified_at is None for item in dataset.schemes) >= 1
    assert all(item.eligibility_verification_status == "unverified" for item in dataset.schemes)
    assert all(item.eligibility_rules == [] for item in dataset.schemes)
    senior_pensions = [
        item for item in dataset.schemes
        if item.category == "Senior Citizens" and item.is_active
    ]
    assert any(item.state == "Sikkim" for item in senior_pensions)


def test_dataset_duplicate_names_are_safely_skipped_and_invalid_rules_rejected(tmp_path: Path, db: Session):
    payload = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    payload["schemes"].append(dict(payload["schemes"][0], name="  " + payload["schemes"][0]["name"].upper() + "  "))
    duplicate_path = tmp_path / "duplicate.json"
    duplicate_path.write_text(json.dumps(payload), encoding="utf-8")
    duplicate_dataset = load_dataset(duplicate_path)
    result = sync_records(db, [duplicate_dataset.schemes[0], duplicate_dataset.schemes[-1]], apply=True)
    db.commit()
    assert result.added == 1 and result.skipped == 1
    assert db.query(Scheme).count() == 1

    payload = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    payload["schemes"][0]["eligibility_rules"] = [{
        "field_name": "not_a_profile_field", "operator": "equals", "value": "x"
    }]
    invalid_path = tmp_path / "invalid-rule.json"
    invalid_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_dataset(invalid_path)


def test_dataset_rejects_non_official_or_insecure_sources(tmp_path: Path):
    payload = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    payload["schemes"][0]["source_url"] = "http://example.com/fake-scheme"
    invalid_path = tmp_path / "invalid-source.json"
    invalid_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises((ValidationError, ValueError)):
        load_dataset(invalid_path)


def test_import_is_idempotent_and_does_not_overwrite_existing_scheme(db: Session):
    dataset = load_dataset()
    existing_name = dataset.schemes[0].name
    prior = Scheme(
        name=existing_name, description="Preserve this description", benefit="Preserve this benefit",
        category="Legacy", is_active=False,
    )
    db.add(prior)
    db.commit()

    inserted, skipped = import_records(db, dataset.schemes)
    db.commit()
    assert inserted == len(dataset.schemes) - 1
    assert skipped == 1
    inserted_again, skipped_again = import_records(db, dataset.schemes)
    db.commit()
    assert (inserted_again, skipped_again) == (0, len(dataset.schemes))

    preserved = db.scalar(select(Scheme).where(Scheme.name == existing_name))
    assert preserved.description == "Preserve this description"
    assert preserved.benefit == "Preserve this benefit"
    assert preserved.category == "Legacy"
    assert preserved.is_active is False
    assert len(db.scalars(select(Scheme.id)).all()) == len(dataset.schemes)
    assert db.scalars(select(EligibilityRule.id)).all() == []


def test_importer_preserves_rule_metadata_and_rule_schema(db: Session):
    dataset = load_dataset()
    row = dataset.schemes[0].model_copy(update={
        "name": "Test-only verified scheme",
        "eligibility_rules": [{
            "field_name": "age", "operator": "gte", "value": "18",
            "group_id": 2, "logical_operator": "AND",
        }],
    })
    inserted, skipped = import_records(db, [row])
    db.commit()
    assert (inserted, skipped) == (1, 0)
    scheme = db.scalar(select(Scheme).where(Scheme.name == row.name))
    assert scheme.source_name == row.source_name
    assert scheme.source_url == row.source_url
    assert scheme.verification_status == "pending"
    assert scheme.eligibility_verification_status == "unverified"
    rule = db.scalar(select(EligibilityRule).where(EligibilityRule.scheme_id == scheme.id))
    assert (rule.field_name, rule.operator, rule.value, rule.group_id, rule.logical_operator) == (
        "age", "gte", "18", 2, "AND"
    )
    assert rule.is_active is False


def test_sync_classifies_unchanged_changes_and_versions_without_overwrite(db: Session):
    original = load_dataset().schemes[0]
    first = sync_records(db, [original], apply=True)
    db.commit()
    assert first.added == 1
    scheme = db.scalar(select(Scheme).where(Scheme.name == original.name))
    original_benefit = scheme.benefit

    same = sync_records(db, [original], apply=True)
    db.commit()
    assert same.unchanged == 1
    assert db.query(SchemeVersion).filter_by(scheme_id=scheme.id).count() == 1

    changed = original.model_copy(update={"benefit": "Changed official benefit pending review"})
    proposal = sync_records(db, [changed], apply=True)
    db.commit()
    assert proposal.updated == 1
    assert scheme.benefit == original_benefit
    versions = db.scalars(select(SchemeVersion).where(SchemeVersion.scheme_id == scheme.id).order_by(SchemeVersion.version_number)).all()
    assert [item.version_number for item in versions] == [1, 2]
    assert versions[1].verification_status == "pending"
    assert versions[1].snapshot["benefit"] == "Changed official benefit pending review"

    retry = sync_records(db, [changed], apply=True)
    db.commit()
    assert retry.unchanged == 1
    assert db.query(SchemeVersion).filter_by(scheme_id=scheme.id).count() == 2


def test_import_history_and_source_registry_are_written(db: Session):
    record = load_dataset().schemes[-1]
    summary = sync_records(db, [record], apply=True)
    db.commit()
    history = db.scalar(select(SchemeImportHistory))
    source = db.scalar(select(SchemeSource).where(SchemeSource.source_url == record.source_url))
    assert summary.added == 1
    assert history.status == "success"
    assert (history.discovered, history.added, history.failed) == (1, 1, 0)
    assert history.completed_at is not None
    assert source.source_name == record.source_name
    # Local curated imports are not live source checks; preserve this distinction.
    assert source.last_checked is None and source.last_successful_sync is None
