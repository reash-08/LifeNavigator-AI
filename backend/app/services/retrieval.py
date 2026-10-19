import re
from collections.abc import Iterable

from sqlalchemy.orm import Session, selectinload

from app.models.scheme import Scheme
from app.schemas.retrieval import RetrievedScheme, SchemeEvidence
from app.services.document_ingestion import retrieve_document_chunks


_WORD = re.compile(r"[\w]+", re.UNICODE)


def _tokens(value: str) -> set[str]:
    return {token.casefold() for token in _WORD.findall(value) if len(token) > 1}


def _criteria(scheme: Scheme) -> list[str]:
    criteria = []
    for rule in scheme.eligibility_rules:
        criteria.append(
            f"{rule.field_name} {rule.operator} {rule.value}"
            + (f" (group {rule.group_id}, {rule.logical_operator or 'AND'})" if rule.group_id is not None else "")
        )
    if criteria:
        return criteria
    for label, value in (
        ("State", scheme.state), ("Minimum age", scheme.min_age),
        ("Maximum age", scheme.max_age), ("Education", scheme.education),
        ("Employment status", scheme.employment_status), ("Category", scheme.category),
        ("Maximum annual income", scheme.max_annual_income),
    ):
        if value is not None:
            criteria.append(f"{label}: {value}")
    return criteria


def _searchable_text(scheme: Scheme) -> str:
    values: Iterable[object] = (
        scheme.name, scheme.description, scheme.category, scheme.subcategory,
        scheme.state, scheme.government_level, scheme.ministry, scheme.department,
        scheme.benefit, scheme.required_documents, scheme.application_process, scheme.source_name,
        *(scheme.beneficiary_groups or []),
        *[f"{rule.field_name} {rule.operator} {rule.value}" for rule in scheme.eligibility_rules],
    )
    return " ".join(str(value) for value in values if value)


def search_schemes(
    db: Session,
    query: str = "",
    *,
    category: str | None = None,
    beneficiary_group: str | None = None,
    state: str | None = None,
    active_only: bool = True,
    limit: int = 10,
) -> list[RetrievedScheme]:
    schemes = db.query(Scheme).options(selectinload(Scheme.eligibility_rules)).all()
    query_terms = _tokens(query)
    generic_words = {"find", "scheme", "schemes", "benefit", "benefits", "yojana", "apply", "support", "subsidy", "grant", "government", "assistance", "how", "what", "where", "can", "want", "need"}
    substantive_query_terms = query_terms - generic_words
    results: list[RetrievedScheme] = []
    for scheme in schemes:
        if active_only and not scheme.is_active:
            continue
        if category and (scheme.category or "").casefold() != category.casefold():
            continue
        if state:
            scheme_state = (scheme.state or "").casefold()
            is_national = not scheme_state or scheme_state in {"all india", "india", "central", "national"} or (scheme.government_level or "").casefold() == "central"
            if not is_national and scheme_state != state.casefold():
                continue
        groups = scheme.beneficiary_groups or []
        if beneficiary_group and not any(beneficiary_group.casefold() in group.casefold() for group in groups):
            continue

        text = _searchable_text(scheme)
        searchable_terms = _tokens(text)
        if substantive_query_terms:
            if not substantive_query_terms.intersection(searchable_terms):
                continue
        elif query_terms and not query_terms.intersection(searchable_terms):
            continue

        # Lexical score component
        score = (len(query_terms & searchable_terms) / len(query_terms)) if query_terms else 0.0
        if query_terms and query_terms & _tokens(scheme.name):
            score += 0.25

        evidence = [SchemeEvidence(
            kind="scheme_metadata",
            text=f"{scheme.name}: {scheme.description} Benefit: {scheme.benefit}",
            source_name=scheme.source_name,
            source_url=scheme.source_url,
            verification_status=scheme.verification_status,
            verified_at=scheme.verified_at,
        )]
        criteria = _criteria(scheme)
        for criterion in criteria:
            evidence.append(SchemeEvidence(
                kind="structured_eligibility",
                text=criterion,
                source_name=scheme.source_name,
                source_url=scheme.source_url,
                verification_status=scheme.verification_status,
                verified_at=scheme.verified_at,
            ))
        for chunk, document, chunk_score in retrieve_document_chunks(db, query, scheme_id=scheme.id, limit=5):
            evidence.append(SchemeEvidence(
                kind="document_chunk", text=chunk.text, source_name=document.source_name,
                source_url=document.source_url, verification_status=scheme.verification_status,
                verified_at=scheme.verified_at, document_id=document.id, chunk_id=chunk.id,
            ))
            score += 0.25 * chunk_score

        results.append(RetrievedScheme(
            id=scheme.id, name=scheme.name, description=scheme.description,
            category=scheme.category, subcategory=scheme.subcategory, state=scheme.state,
            government_level=scheme.government_level, beneficiary_groups=groups,
            benefit=scheme.benefit, application_url=scheme.application_url,
            application_process=scheme.application_process,
            source_name=scheme.source_name, source_url=scheme.source_url,
            verification_status=scheme.verification_status, verified_at=scheme.verified_at,
            score=round(score, 4), evidence=evidence,
            eligibility_rules=list(scheme.eligibility_rules), known_criteria=criteria,
            criteria_completeness="recorded" if criteria else "not_recorded",
        ))
    results.sort(key=lambda item: (-item.score, item.name.casefold(), item.id))
    return results[:limit]
