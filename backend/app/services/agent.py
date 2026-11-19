"""Safe deterministic orchestration for benefit discovery and eligibility."""
from dataclasses import dataclass
from hashlib import sha256
import re

from sqlalchemy.orm import Session

from app.models.profile import UserProfile
from app.schemas.agent import AgentResponse, AgentSchemeResult, AgentSource
from app.services.eligibility import check_scheme_eligibility
from app.services.explanation import ExplanationProvider, GroundedTemplateProvider, get_explanation_provider
from app.services.retrieval import search_schemes


@dataclass(frozen=True)
class QueryIntent:
    kind: str
    eligibility: bool
    category: str | None = None
    state: str | None = None
    beneficiary_group: str | None = None


_ELIGIBILITY = re.compile(r"\b(eligible|eligibility|qualif(?:y|ies|ied)|can i apply|am i eligible)\b", re.I)
_GENERIC = re.compile(r"^(help|hello|hi|benefits?|schemes?|what should i do)[?.! ]*$", re.I)
_STATES = ("Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal", "Delhi", "Jammu and Kashmir", "Ladakh")
_CATEGORIES = ("Agriculture, Rural & Environment", "Education & Learning", "Health & Wellness", "Housing & Shelter", "Social welfare & Empowerment", "Banking, Financial Services and Insurance", "Business & Entrepreneurship", "Skills & Employment")


def extract_intent(query: str) -> QueryIntent:
    text = query.strip()
    folded = text.casefold()
    eligibility = bool(_ELIGIBILITY.search(text))
    state = next((item for item in _STATES if item.casefold() in folded), None)
    category = next((item for item in _CATEGORIES if item.casefold() in folded), None)
    group = next((word for word in ("farmer", "farmers", "student", "students", "fisher", "fishers", "women", "senior citizen", "persons with disability") if word in folded), None)
    return QueryIntent("eligibility" if eligibility else "discovery", eligibility, category, state, group)


def _ambiguous(query: str) -> bool:
    return bool(_GENERIC.fullmatch(query.strip())) or len(re.findall(r"\w+", query)) < 2


def run_agent(db: Session, *, query: str, profile: UserProfile | None,
              provider: ExplanationProvider | None = None) -> AgentResponse:
    # Keep direct service callers consistent with the API's input contract.
    query = query.strip()
    intent = extract_intent(query)
    if _ambiguous(query):
        return AgentResponse(intent=intent.kind,
            answer="Please share what kind of support you need, such as education, farming, housing, or healthcare, and your state.",
            needs_clarification=True, insufficient_evidence=True, schemes=[], sources=[])

    matches = search_schemes(db, query, category=intent.category, state=intent.state,
                             beneficiary_group=intent.beneficiary_group, limit=8)
    if intent.eligibility and profile is not None:
        # The rule engine alone produces eligibility outcomes. Keep unknown criteria explicit.
        from sqlalchemy.orm import selectinload
        from app.models.scheme import Scheme
        schemes = {s.id: s for s in db.query(Scheme).options(selectinload(Scheme.eligibility_rules)).filter(Scheme.id.in_([m.id for m in matches])).all()} if matches else {}
    else:
        schemes = {}

    results = []
    sources = []
    source_keys = set()
    for match in matches:
        eligibility_label = None
        reasons: list[str] = []
        missing_fields: list[str] = []
        if intent.eligibility:
            if profile is None:
                eligibility_label = "profile_required"
                reasons = ["Create a profile to compare your details with the recorded rules."]
            elif match.id in schemes:
                assessment = check_scheme_eligibility(profile, schemes[match.id])
                reasons = assessment.reasons
                if assessment.status == "eligible":
                    eligibility_label = "eligible"
                elif assessment.status == "ineligible":
                    eligibility_label = "not_eligible"
                else:
                    eligibility_label = "not_confirmed"
                missing_fields = assessment.missing_fields
            else:
                eligibility_label = "not_evaluated"
        if not missing_fields:
            missing_fields = sorted({
                reason.split(" is missing", 1)[0]
                for reason in reasons
                if " is missing" in reason
            })
        results.append(AgentSchemeResult(scheme_id=match.id, name=match.name,
            eligibility=eligibility_label, eligibility_reasons=reasons,
            next_steps=[step for step in ("Review the cited official scheme information.",
                         "Check the application portal for current dates and required documents.")],
            missing_profile_fields=missing_fields, source_url=match.source_url,
            application_url=match.application_url))
        for ev in match.evidence:
            # Cite only actual stored evidence and preserve its provenance; never fabricate a URL.
            if not ev.text.strip():
                continue
            key = (match.id, ev.kind, ev.document_id, ev.chunk_id, ev.text)
            if key in source_keys:
                continue
            source_keys.add(key)
            evidence_identity = "|".join((ev.kind, str(ev.document_id or ""),
                str(ev.chunk_id or ""), ev.text))
            source_token = sha256(evidence_identity.encode("utf-8")).hexdigest()[:12]
            sources.append(AgentSource(source_id=f"scheme-{match.id}-{ev.kind}-{source_token}",
                scheme_id=match.id, scheme_name=match.name, kind=ev.kind, text=ev.text,
                source_name=ev.source_name, source_url=ev.source_url,
                verification_status=ev.verification_status, verified_at=ev.verified_at,
                document_id=ev.document_id, chunk_id=ev.chunk_id))

    # A result is grounded only when its cited evidence has an excerpt and URL.
    enough = bool(matches) and (not intent.eligibility or profile is not None) and any(
        source.text.strip() and source.source_url for source in sources
    )
    provider = provider or get_explanation_provider()
    if intent.eligibility and profile is not None and results:
        # Explain structured outcomes from the engine; evidence remains separately cited.
        answer = "Eligibility was checked against recorded structured rules. See each scheme's result and reasons; missing profile fields may prevent confirmation."
    elif enough:
        evidence = [
            {
                "text": source.text,
                "source_name": source.source_name,
                "scheme_name": source.scheme_name,
                "kind": source.kind,
            }
            for source in sources
            if source.source_url
        ]
        answer = provider.explain(question=query, evidence=evidence)
    else:
        answer = "I could not find enough source-backed information to answer this request. Try adding the benefit type, your state, or a scheme name."
    return AgentResponse(intent=intent.kind, answer=answer, needs_clarification=False,
        insufficient_evidence=not enough, schemes=results, sources=sources)
