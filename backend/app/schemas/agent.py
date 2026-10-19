from typing import Literal
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AgentQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    query: str = Field(min_length=3, max_length=500)

    @field_validator("query")
    @classmethod
    def query_must_contain_words(cls, value: str) -> str:
        if not any(character.isalnum() for character in value):
            raise ValueError("query must contain at least one letter or number")
        return value


class AgentSource(BaseModel):
    source_id: str
    scheme_id: int
    scheme_name: str
    kind: Literal["scheme_metadata", "structured_eligibility", "document_chunk"]
    text: str
    source_name: str | None = None
    source_url: str | None = None
    verification_status: str | None = None
    verified_at: date | None = None
    document_id: int | None = None
    chunk_id: int | None = None


class AgentSchemeResult(BaseModel):
    scheme_id: int
    name: str
    eligibility: Literal["eligible", "not_eligible", "not_confirmed", "profile_required", "not_evaluated"] | None = None
    eligibility_reasons: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    missing_profile_fields: list[str] = Field(default_factory=list)
    source_url: str | None = None
    application_url: str | None = None


class AgentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal["discovery", "eligibility"]
    answer: str
    needs_clarification: bool
    insufficient_evidence: bool
    schemes: list[AgentSchemeResult]
    sources: list[AgentSource]
