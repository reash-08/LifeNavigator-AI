from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SchemeVersionReview(BaseModel):
    decision: Literal["verified", "rejected", "expired"]
    eligibility_verification_status: Literal["unverified", "verified", "not_confirmed"] = "unverified"
    verified_at: date | None = None
    effective_from: date | None = None
    effective_until: date | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_period(self):
        if self.effective_from and self.effective_until and self.effective_until < self.effective_from:
            raise ValueError("effective_until cannot precede effective_from")
        if self.eligibility_verification_status == "verified" and self.decision != "verified":
            raise ValueError("eligibility can only be verified with an approved scheme version")
        return self


class PendingSchemeVersion(BaseModel):
    id: int
    scheme_id: int
    scheme_name: str
    version_number: int
    snapshot: dict
    source_url: str | None
    verification_status: str
    eligibility_verification_status: str
    imported_at: datetime
    change_summary: str | None

    model_config = ConfigDict(from_attributes=True)
