import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.models.eligibility_rule import EligibilityRule
from app.models.profile import UserProfile
from app.models.scheme import Scheme


SUPPORTED_OPERATORS = {"equals", "not_equals", "lt", "lte", "gt", "gte", "in", "not_in", "contains"}

_SOCIAL_CATEGORY_PATTERNS = {
    "SC": re.compile(r"\b(sc|scheduled\s+caste|scheduled\s+castes)\b", re.IGNORECASE),
    "ST": re.compile(r"\b(st|scheduled\s+tribe|scheduled\s+tribes)\b", re.IGNORECASE),
    "OBC": re.compile(r"\b(obc|other\s+backward\s+class(?:es)?|ebc|dnt)\b", re.IGNORECASE),
    "EWS": re.compile(r"\b(ews|economically\s+weaker\s+section(?:s)?)\b", re.IGNORECASE),
    "General": re.compile(r"\b(general\s+category|open\s+category)\b", re.IGNORECASE),
}


@dataclass
class EligibilityAssessment:
    """Structured assessment contract returned by the eligibility engine.

    Provides 100% backward-compatibility for callers unpacking (eligible, reasons)
    or checking equality against 2-tuples, while providing explicit assessment status
    and missing_fields.
    """
    eligible: bool
    reasons: list[str]
    status: str  # "eligible", "ineligible", "needs_more_info", "unverified"
    missing_fields: list[str] = field(default_factory=list)

    def __iter__(self):
        yield self.eligible
        yield self.reasons

    def __getitem__(self, idx):
        return (self.eligible, self.reasons)[idx]

    def __len__(self):
        return 2

    def __bool__(self):
        return self.eligible

    def __eq__(self, other):
        if isinstance(other, tuple) and len(other) == 2:
            return (self.eligible, self.reasons) == other
        if isinstance(other, EligibilityAssessment):
            return (
                self.eligible == other.eligible
                and self.reasons == other.reasons
                and self.status == other.status
                and self.missing_fields == other.missing_fields
            )
        return False


def _parse_scalar_value(raw_value: Any, profile_value: Any) -> Any:
    if isinstance(profile_value, bool):
        if isinstance(raw_value, bool):
            return raw_value
        normalized = str(raw_value).strip().casefold()
        if normalized not in {"true", "false", "1", "0", "yes", "no"}:
            raise ValueError("expected a boolean")
        return normalized in {"true", "1", "yes"}
    if isinstance(profile_value, int):
        return int(raw_value)
    if isinstance(profile_value, float):
        return float(raw_value)
    return str(raw_value)


def _parse_rule_value(raw_value: str, profile_value: Any, operator: str) -> Any:
    if operator in {"in", "not_in"}:
        values = json.loads(raw_value)
        if not isinstance(values, list) or not values:
            raise ValueError("expected a non-empty JSON array")
        return [_parse_scalar_value(item, profile_value) for item in values]
    return _parse_scalar_value(raw_value, profile_value)


def _matches_rule(profile: UserProfile, rule: EligibilityRule) -> tuple[bool, str, bool, str | None]:
    """Evaluates a single eligibility rule against the user profile.

    Returns:
        (matched, description, is_missing, missing_field_name)
    """
    field_name = rule.field_name
    description = f"{field_name} {rule.operator} {rule.value}"
    if field_name not in UserProfile.__table__.columns or field_name in {"id", "user_id"}:
        return False, f"Invalid eligibility field: {field_name}", False, None
    if rule.operator not in SUPPORTED_OPERATORS:
        return False, f"Unsupported operator: {rule.operator}", False, None

    profile_value = getattr(profile, field_name, None)
    if profile_value is None:
        return False, f"{field_name} is missing", True, field_name

    try:
        expected = _parse_rule_value(rule.value, profile_value, rule.operator)
        left = profile_value
        if isinstance(profile_value, str):
            left = profile_value.casefold()
            if isinstance(expected, str):
                expected = expected.casefold()
            elif isinstance(expected, list):
                expected = [str(value).casefold() for value in expected]
        elif isinstance(profile_value, (list, tuple, set)):
            left = [item.casefold() if isinstance(item, str) else item for item in profile_value]
            if isinstance(expected, str):
                expected = expected.casefold()
            elif isinstance(expected, list):
                expected = [item.casefold() if isinstance(item, str) else item for item in expected]

        comparisons = {
            "equals": lambda: left == expected,
            "not_equals": lambda: left != expected,
            "lt": lambda: left < expected,
            "lte": lambda: left <= expected,
            "gt": lambda: left > expected,
            "gte": lambda: left >= expected,
            "in": lambda: left in expected,
            "not_in": lambda: left not in expected,
            "contains": lambda: expected in left,
        }
        matched = comparisons[rule.operator]()
    except (TypeError, ValueError, json.JSONDecodeError):
        return False, f"Invalid rule value for {field_name}", False, None

    return matched, description, False, None


def _check_dynamic_rules(
    profile: UserProfile,
    rules: list[EligibilityRule],
) -> EligibilityAssessment:
    groups: dict[int | None, list[EligibilityRule]] = defaultdict(list)
    for rule in rules:
        groups[rule.group_id].append(rule)

    reasons: list[str] = []
    all_groups_passed = True
    has_explicit_failure = False
    has_missing_info = False
    missing_fields_set: set[str] = set()

    for group_id, group_rules in groups.items():
        raw_operator = (group_rules[0].logical_operator or "AND").upper()
        if raw_operator not in {"AND", "OR"}:
            raw_operator = "AND"
            matches = [(False, f"Invalid logical operator in rule group {group_id}", False, None)]
        else:
            matches = [_matches_rule(profile, rule) for rule in group_rules]

        passed = all(match for match, _, _, _ in matches) if raw_operator == "AND" else any(match for match, _, _, _ in matches)
        label = f"Rule group {group_id}" if group_id is not None else "Rules"
        if passed:
            matched = [description for ok, description, _, _ in matches if ok]
            reasons.append(f"{label} matched ({raw_operator}): {', '.join(matched)}")
        else:
            all_groups_passed = False
            failures = [description for match, description, _, _ in matches if not match]
            reasons.append(f"{label} did not match ({raw_operator}): {', '.join(failures)}")

            if raw_operator == "AND":
                group_has_explicit = any(not ok and not is_missing for ok, _, is_missing, _ in matches)
                group_has_missing = any(not ok and is_missing for ok, _, is_missing, _ in matches)
                if group_has_explicit:
                    has_explicit_failure = True
                if group_has_missing:
                    has_missing_info = True
                    for _, _, is_missing, field in matches:
                        if is_missing and field:
                            missing_fields_set.add(field)
            else:  # OR
                group_has_missing = any(is_missing for _, _, is_missing, _ in matches)
                if group_has_missing:
                    has_missing_info = True
                    for _, _, is_missing, field in matches:
                        if is_missing and field:
                            missing_fields_set.add(field)
                else:
                    has_explicit_failure = True

    if all_groups_passed:
        status = "eligible"
        eligible = True
    elif has_explicit_failure:
        status = "ineligible"
        eligible = False
    elif has_missing_info:
        status = "needs_more_info"
        eligible = False
    else:
        status = "ineligible"
        eligible = False

    return EligibilityAssessment(
        eligible=eligible,
        reasons=reasons,
        status=status,
        missing_fields=sorted(missing_fields_set),
    )


def _evaluate_beneficiary_group_categories(
    profile: UserProfile,
    beneficiary_groups: list[str] | None,
) -> tuple[bool, bool, str | None, str | None]:
    """Evaluates whether documented beneficiary groups impose a social category requirement.

    Returns:
        (has_requirement, passed, reason, missing_field)
    """
    if not beneficiary_groups or not isinstance(beneficiary_groups, list):
        return False, True, None, None

    categories_found = set()
    for group_str in beneficiary_groups:
        if not isinstance(group_str, str):
            continue
        for cat, pattern in _SOCIAL_CATEGORY_PATTERNS.items():
            if pattern.search(group_str):
                categories_found.add(cat)

    if not categories_found:
        return False, True, None, None

    broad_indicators = re.compile(
        r"\b(all|farmers?|fishers?|general|households?|poor|vendors?|artisans?|citizens?|entrepreneurs?|msme|workers?)\b",
        re.IGNORECASE,
    )
    non_category_broad_groups = []
    for group_str in beneficiary_groups:
        if not isinstance(group_str, str):
            continue
        has_cat = any(pattern.search(group_str) for pattern in _SOCIAL_CATEGORY_PATTERNS.values())
        if not has_cat and broad_indicators.search(group_str):
            non_category_broad_groups.append(group_str)

    if non_category_broad_groups:
        return False, True, None, None

    profile_cat = getattr(profile, "category", None)
    if not profile_cat or not str(profile_cat).strip():
        return (
            True,
            False,
            "Social category information is missing for scheme with targeted beneficiary groups",
            "category",
        )

    normalized_profile_cat = str(profile_cat).strip().casefold()
    matched = False
    for cat in categories_found:
        if cat.casefold() == normalized_profile_cat:
            matched = True
            break
        if cat == "SC" and normalized_profile_cat in {"sc", "scheduled caste", "scheduled castes"}:
            matched = True
            break
        if cat == "ST" and normalized_profile_cat in {"st", "scheduled tribe", "scheduled tribes"}:
            matched = True
            break
        if cat == "OBC" and normalized_profile_cat in {"obc", "other backward class", "other backward classes", "ebc", "dnt"}:
            matched = True
            break
        if cat == "EWS" and normalized_profile_cat in {"ews", "economically weaker section", "economically weaker sections"}:
            matched = True
            break

    if matched:
        return True, True, "Social category matches documented beneficiary-group requirements", None

    sorted_cats = ", ".join(sorted(categories_found))
    return (
        True,
        False,
        f"Social category does not match documented beneficiary groups. Required: {sorted_cats}",
        None,
    )


def check_scheme_eligibility(
    profile: UserProfile,
    scheme: Scheme
) -> EligibilityAssessment:
    if not scheme.is_active:
        return EligibilityAssessment(
            eligible=False,
            reasons=["Scheme is currently inactive"],
            status="ineligible",
            missing_fields=[],
        )

    if scheme.verification_status != "verified" or not scheme.source_url:
        return EligibilityAssessment(
            eligible=False,
            reasons=["Eligibility is not confirmed from a verified official source"],
            status="unverified",
            missing_fields=[],
        )
    registered_source = getattr(scheme, "source", None)
    if (
        registered_source is None
        or not registered_source.is_active
        or registered_source.source_url != scheme.source_url
    ):
        return EligibilityAssessment(
            eligible=False,
            reasons=["Eligibility source is not registered or active"],
            status="unverified",
            missing_fields=[],
        )
    if scheme.eligibility_verification_status != "verified":
        return EligibilityAssessment(
            eligible=False,
            reasons=["Eligibility criteria have not been verified; check the official source"],
            status="unverified",
            missing_fields=[],
        )

    verified_versions = [
        version for version in getattr(scheme, "versions", [])
        if version.verification_status == "verified"
    ]
    if verified_versions:
        current_version = max(verified_versions, key=lambda version: version.version_number)
        if current_version.effective_until is not None and current_version.effective_until < date.today():
            return EligibilityAssessment(
                eligible=False,
                reasons=["The verified scheme version has expired"],
                status="ineligible",
                missing_fields=[],
            )
        if current_version.effective_from is not None and current_version.effective_from > date.today():
            return EligibilityAssessment(
                eligible=False,
                reasons=["The verified scheme version is not yet effective"],
                status="ineligible",
                missing_fields=[],
            )

    # SQLAlchemy column defaults are applied at INSERT/flush time; unsaved,
    # explicitly constructed rules in callers/tests should remain active.
    rules = [rule for rule in scheme.eligibility_rules if getattr(rule, "is_active", True) is not False]
    if rules:
        return _check_dynamic_rules(profile, rules)

    reasons = ["Using legacy scheme criteria; add eligibility rules to use dynamic matching"]
    criteria_seen = False
    missing_fields_set: set[str] = set()
    explicit_failures: list[str] = []

    if scheme.state is not None:
        criteria_seen = True
        actual_state = getattr(profile, "state", None)
        if not actual_state:
            missing_fields_set.add("state")
            reasons.append("State information is missing")
        elif actual_state.casefold() != scheme.state.casefold():
            explicit_failures.append(f"State does not match. Required: {scheme.state}")
        else:
            reasons.append("State matches")

    if scheme.min_age is not None or scheme.max_age is not None:
        criteria_seen = True
        actual_age = getattr(profile, "age", None)
        if actual_age is None:
            missing_fields_set.add("age")
            reasons.append("Age information is missing")
        else:
            age_ok = True
            if scheme.min_age is not None and actual_age < scheme.min_age:
                explicit_failures.append(f"Age is below the minimum requirement of {scheme.min_age}")
                age_ok = False
            if scheme.max_age is not None and actual_age > scheme.max_age:
                explicit_failures.append(f"Age exceeds the maximum requirement of {scheme.max_age}")
                age_ok = False
            if age_ok:
                reasons.append("Age is within the required range")

    for field_name, expected, label in (
        ("education", scheme.education, "Education"),
        ("employment_status", scheme.employment_status, "Employment status"),
    ):
        if expected is None:
            continue
        criteria_seen = True
        actual = getattr(profile, field_name, None)
        if not actual:
            missing_fields_set.add(field_name)
            reasons.append(f"{label} information is missing")
        elif actual.casefold() != expected.casefold():
            explicit_failures.append(f"{label} does not match. Required: {expected}")
        else:
            reasons.append(f"{label} matches")

    if scheme.max_annual_income is not None:
        criteria_seen = True
        actual_income = getattr(profile, "annual_income", None)
        if actual_income is None:
            missing_fields_set.add("annual_income")
            reasons.append("Annual income information is missing")
        elif actual_income > scheme.max_annual_income:
            explicit_failures.append(f"Annual income exceeds the maximum limit of {scheme.max_annual_income}")
        else:
            reasons.append("Income is within the permitted limit")

    has_cat_req, cat_passed, cat_reason, cat_missing = _evaluate_beneficiary_group_categories(
        profile, getattr(scheme, "beneficiary_groups", None)
    )
    if has_cat_req:
        criteria_seen = True
        if cat_missing:
            missing_fields_set.add(cat_missing)
            reasons.append(cat_reason)
        elif not cat_passed:
            explicit_failures.append(cat_reason)
        else:
            reasons.append(cat_reason)

    if not criteria_seen:
        return EligibilityAssessment(
            eligible=False,
            reasons=["No verified eligibility criteria are recorded"],
            status="unverified",
            missing_fields=[],
        )

    if explicit_failures:
        return EligibilityAssessment(
            eligible=False,
            reasons=explicit_failures,
            status="ineligible",
            missing_fields=sorted(missing_fields_set),
        )

    if missing_fields_set:
        missing_reasons = [r for r in reasons if "is missing" in r]
        return EligibilityAssessment(
            eligible=False,
            reasons=missing_reasons if missing_reasons else ["Required profile information is missing"],
            status="needs_more_info",
            missing_fields=sorted(missing_fields_set),
        )

    return EligibilityAssessment(
        eligible=True,
        reasons=reasons,
        status="eligible",
        missing_fields=[],
    )
