from pydantic import BaseModel, ConfigDict
from datetime import date


class EligibleSchemeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    state: str | None
    government_level: str | None = None
    ministry: str | None = None
    department: str | None = None
    beneficiary_groups: list[str] | None = None
    source_url: str | None = None
    source_name: str | None = None
    verified_at: date | None = None
    verification_status: str | None = None
    eligibility_verification_status: str = "unverified"
    min_age: int | None
    max_age: int | None
    education: str | None
    employment_status: str | None
    category: str | None
    subcategory: str | None = None
    max_annual_income: int | None
    benefit: str
    required_documents: str | None
    application_process: str | None = None
    application_url: str | None
    application_deadline: date | None
    is_active: bool

    eligible: bool
    reasons: list[str]
    assessment_status: str | None = None
    missing_fields: list[str] | None = None
