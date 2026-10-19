"""Stage 3C Manifest Validation Script.

Validates the cryptographic checksum, schema, and relational integrity
of a Stage 3C identity export manifest.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import re
import sys
from pathlib import Path

SLUG_REGEX = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

def validate_manifest(manifest_path: Path, expected_count: int = 130) -> bool:
    if not manifest_path.exists():
        print(f"FAIL: Manifest file not found at {manifest_path}")
        return False

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"FAIL: Manifest is not valid JSON: {exc}")
        return False

    records = data.get("records")
    if not isinstance(records, list):
        print("FAIL: Manifest does not contain a 'records' list.")
        return False

    # 1. Verify record count
    if len(records) != expected_count:
        print(f"FAIL: Expected {expected_count} records, found {len(records)}.")
        return False
    print(f"PASS: Total record count matches expected ({len(records)}).")

    # 2. Verify SHA-256 Checksum
    expected_hash = data.get("sha256")
    canonical_payload = json.dumps(records, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    computed_hash = sha256(canonical_payload.encode("utf-8")).hexdigest()
    if computed_hash != expected_hash:
        print(f"FAIL: SHA-256 Checksum mismatch! Manifest={expected_hash}, Computed={computed_hash}")
        return False
    print(f"PASS: Manifest SHA-256 checksum verified ({computed_hash}).")

    # 3. Verify slug format, length, and uniqueness per jurisdiction
    active_slugs_by_jurisdiction: dict[str, set[str]] = {}
    record_by_id = {r["id"]: r for r in records}

    for r in records:
        sid = r.get("id")
        slug = r.get("slug")
        juris = r.get("jurisdiction", "CENTRAL")
        is_active = r.get("is_active", True)
        canonical_id = r.get("canonical_scheme_id")

        if not slug or not isinstance(slug, str):
            print(f"FAIL: Scheme ID {sid} has invalid/empty slug: {slug}")
            return False

        if len(slug) > 80:
            print(f"FAIL: Scheme ID {sid} slug exceeds 80 characters ({len(slug)}): '{slug}'")
            return False

        if not SLUG_REGEX.match(slug):
            print(f"FAIL: Scheme ID {sid} slug contains invalid characters: '{slug}'")
            return False

        if is_active:
            juris_set = active_slugs_by_jurisdiction.setdefault(juris, set())
            if slug in juris_set:
                print(f"FAIL: Duplicate active slug in jurisdiction '{juris}': '{slug}'")
                return False
            juris_set.add(slug)

            if canonical_id is not None:
                print(f"FAIL: Active scheme ID {sid} cannot have canonical_scheme_id ({canonical_id}).")
                return False
        else:
            if canonical_id is not None:
                target = record_by_id.get(canonical_id)
                if not target:
                    print(f"FAIL: Inactive scheme ID {sid} points to non-existent target ID {canonical_id}.")
                    return False
                if not target.get("is_active"):
                    print(f"FAIL: Scheme ID {sid} points to INACTIVE target ID {canonical_id}.")
                    return False
                if target.get("canonical_scheme_id") is not None:
                    print(f"FAIL: Target ID {canonical_id} itself has a redirect, violating 1-hop invariant.")
                    return False

    print("PASS: All slugs are valid ASCII, length <= 80, and unique per active jurisdiction.")
    print("PASS: Canonical redirect integrity confirmed (1-hop terminal link to active scheme).")
    print(f"\nManifest {manifest_path.name} is VALID and VERIFIED.")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate Stage 3C manifest.")
    parser.add_argument("manifest_path", help="Path to manifest JSON file")
    parser.add_argument("--expected-count", type=int, default=130, help="Expected record count")
    args = parser.parse_args()

    success = validate_manifest(Path(args.manifest_path), args.expected_count)
    sys.exit(0 if success else 1)
