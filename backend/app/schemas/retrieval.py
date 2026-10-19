from datetime import date

from pydantic import BaseModel

from app.schemas.eligibility_rule import EligibilityRuleResponse


class SchemeEvidence(BaseModel):
    kind: str
    text: str
    source_name: str | None = None
    source_url: str | None = None
    verification_status: str | None = None
    verified_at: date | None = None
    document_id: int | None = None
    chunk_id: int | None = None


class RetrievedScheme(BaseModel):
    id: int
    name: str
    description: str
    category: str | None = None
    subcategory: str | None = None
    state: str | None = None
    government_level: str | None = None
    beneficiary_groups: list[str] | None = None
    benefit: str
    application_url: str | None = None
    application_process: str | None = None
    source_name: str | None = None
    source_url: str | None = None
    verification_status: str | None = None
    verified_at: date | None = None
    score: float
    evidence: list[SchemeEvidence]
    eligibility_rules: list[EligibilityRuleResponse]
    known_criteria: list[str]
    criteria_completeness: str


class SchemeSearchResponse(BaseModel):
    query: str
    results: list[RetrievedScheme]
