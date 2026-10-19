"""Deterministic scheme slug generation and collision resolution."""

from __future__ import annotations

import re
import unicodedata
from hashlib import sha256


def truncate_slug(slug: str, max_len: int = 80) -> str:
    """Truncate slug at a word/hyphen boundary so length <= max_len."""
    slug = re.sub(r"-+", "-", slug).strip("-")
    if len(slug) <= max_len:
        return slug
    truncated = slug[:max_len]
    last_dash = truncated.rfind("-")
    if last_dash > 20:
        return truncated[:last_dash].strip("-")
    return truncated.strip("-")


INDIAN_JURISDICTIONS = {
    "tamil nadu", "karnataka", "maharashtra", "kerala", "odisha", "sikkim",
    "gujarat", "rajasthan", "punjab", "haryana", "bihar", "assam", "telangana",
    "andhra pradesh", "west bengal", "uttar pradesh", "madhya pradesh", "delhi",
    "goa", "jammu and kashmir", "jharkhand", "chhattisgarh", "uttarakhand",
    "himachal pradesh", "manipur", "meghalaya", "mizoram", "nagaland", "tripura",
    "puducherry", "ladakh", "central", "urban", "grameen",
}


def generate_base_slug(name: str) -> str:
    """Generate a clean, deterministic, ASCII-only base slug from a scheme title."""
    # 1. Check for official acronym or short title in parentheses, e.g. (PM-KISAN), (PMAY-U 2.0), (Pudhumai Penn)
    for m in re.finditer(r"\(([a-zA-Z0-9\-\.\s,/]{2,35})\)", name):
        content = m.group(1).strip()
        parts = [p.strip() for p in re.split(r"[,/]", content)]
        for part in parts:
            clean_part = re.sub(r"[^a-zA-Z0-9\-]", "", part.replace(" ", "-")).lower()
            clean_part = re.sub(r"-+", "-", clean_part).strip("-")
            if not clean_part or len(clean_part) < 2:
                continue
            if part.lower() in INDIAN_JURISDICTIONS or clean_part.replace("-", " ") in INDIAN_JURISDICTIONS:
                continue
            if len(clean_part) <= 20:
                return truncate_slug(clean_part, 80)

    # 2. Unicode normalization & dash unification
    text = unicodedata.normalize("NFKD", name)
    text = text.replace("—", "-").replace("–", "-").replace("&", "and")

    # 3. Strip non-ASCII and punctuation
    clean = re.sub(r"[^a-zA-Z0-9\s\-]", "", text).lower()
    words = clean.split()
    if words:
        raw_slug = "-".join(words)
        return truncate_slug(raw_slug, 80)

    # 4. Pure native Indic script fallback (zero Latin characters)
    name_hash = sha256(name.encode("utf-8")).hexdigest()[:8]
    return f"scheme-indic-{name_hash}"


def resolve_slug_collision(
    base_slug: str,
    existing_slugs: set[str],
    name: str = "",
    source_url: str = "",
    jurisdiction: str = "CENTRAL",
    ministry: str | None = None,
) -> str:
    """Deterministically resolve slug collisions within a jurisdiction."""
    if base_slug not in existing_slugs:
        return base_slug

    # Step 1: Disambiguate with ministry / department acronym if provided
    if ministry:
        dept_match = re.search(r"\(([A-Z0-9\-]{2,10})\)", ministry)
        dept_code = dept_match.group(1).lower() if dept_match else None
        if not dept_code:
            dept_words = [w[0].lower() for w in re.sub(r"[^a-zA-Z\s]", "", ministry).split() if len(w) > 2]
            dept_code = "".join(dept_words[:5]) if dept_words else None
        if dept_code:
            candidate_1 = truncate_slug(f"{base_slug}-{dept_code}", 80)
            if candidate_1 not in existing_slugs:
                return candidate_1

    # Step 2: Deterministic 4-character stable content hash
    stable_payload = f"{name}|{source_url or ''}|{jurisdiction.upper()}"
    hash_suffix = sha256(stable_payload.encode("utf-8")).hexdigest()[:4]
    candidate_2 = f"{truncate_slug(base_slug, 75)}-{hash_suffix}"
    if candidate_2 not in existing_slugs:
        return candidate_2

    # Step 3: Deterministic sequence fallback
    for seq in range(2, 100):
        candidate_seq = f"{truncate_slug(base_slug, 76)}-{seq}"
        if candidate_seq not in existing_slugs:
            return candidate_seq

    # Fallback with timestamp hash
    return f"{truncate_slug(base_slug, 70)}-{sha256(stable_payload.encode()).hexdigest()[:8]}"
