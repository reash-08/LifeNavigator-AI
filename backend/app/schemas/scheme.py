from datetime import date

from pydantic import AliasChoices, BaseModel, Field, model_validator
from app.schemas.eligibility_rule import EligibilityRuleResponse


class SchemeCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    description: str = Field(min_length=1)

    state: str | None = Field(default=None, max_length=100)
    government_level: str | None = Field(default=None, max_length=30)
    ministry: str | None = Field(default=None, max_length=200)
    department: str | None = Field(default=None, max_length=200)
    beneficiary_groups: list[str] | None = None
    source_url: str | None = Field(default=None, max_length=500)
    source_name: str | None = Field(default=None, max_length=200)
    verified_at: date | None = None
    verification_status: str | None = Field(default=None, max_length=30)
    eligibility_verification_status: str = Field(default="unverified", max_length=30)

    min_age: int | None = Field(default=None, ge=0, le=120)
    max_age: int | None = Field(default=None, ge=0, le=120)

    education: str | None = Field(default=None, max_length=100)
    employment_status: str | None = Field(default=None, max_length=100)
    category: str | None = Field(default=None, max_length=100)
    subcategory: str | None = Field(default=None, max_length=100)

    max_annual_income: int | None = Field(default=None, ge=0)

    benefit: str = Field(min_length=1)
    required_documents: str | None = None
    application_process: str | None = None

    application_url: str | None = Field(default=None, max_length=500)

    application_deadline: date | None = None

    is_active: bool = True

    # Stage 3C Identity & Deduplication fields
    slug: str | None = Field(default=None, max_length=80)
    aliases: list[str] = Field(default_factory=list)
    canonical_scheme_id: int | None = None


    @model_validator(mode="after")
    def validate_scheme_metadata(self):
        if self.government_level and self.government_level.casefold() not in {"central", "state", "ut", "local"}:
            raise ValueError("government_level must be central, state, ut, or local")
        if self.verification_status and self.verification_status.casefold() not in {"pending", "verified", "rejected", "expired", "unverified", "review_needed"}:
            raise ValueError("unsupported verification_status")
        if self.eligibility_verification_status.casefold() not in {"unverified", "verified", "not_confirmed"}:
            raise ValueError("eligibility_verification_status must be unverified, verified, or not_confirmed")
        if self.beneficiary_groups is not None:
            cleaned = [item.strip() for item in self.beneficiary_groups]
            if any(not item for item in cleaned):
                raise ValueError("beneficiary_groups cannot contain empty labels")
            self.beneficiary_groups = list(dict.fromkeys(cleaned))
        return self

    @model_validator(mode="after")
    def validate_age_range(self):
        if self.min_age is not None and self.max_age is not None and self.min_age > self.max_age:
            raise ValueError("min_age cannot be greater than max_age")
        return self


class SchemeResponse(BaseModel):
    id: int
    name: str
    description: str

    state: str | None = None
    government_level: str | None = None
    ministry: str | None = None
    department: str | None = None
    beneficiary_groups: list[str] | None = None
    source_url: str | None = None
    source_name: str | None = None
    verified_at: date | None = None
    verification_status: str | None = None
    eligibility_verification_status: str = "unverified"

    min_age: int | None = None
    max_age: int | None = None

    education: str | None = None
    employment_status: str | None = None
    category: str | None = None
    subcategory: str | None = None

    max_annual_income: int | None = None

    benefit: str
    required_documents: str | None = None
    application_process: str | None = None

    application_url: str | None = None

    application_deadline: date | None = None

    is_active: bool

    # Stage 3C Identity & Deduplication fields
    slug: str | None = None
    aliases: list[str] = Field(default_factory=list)
    canonical_scheme_id: int | None = None

    eligibility_rules: list[EligibilityRuleResponse] = Field(
        default_factory=list,
        validation_alias=AliasChoices("effective_eligibility_rules", "eligibility_rules"),
    )

    class Config:
        from_attributes = True
