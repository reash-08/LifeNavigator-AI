from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


RuleOperator = Literal[
    "equals", "not_equals", "lt", "lte", "gt", "gte",
    "in", "not_in", "contains",
]
LogicalOperator = Literal["AND", "OR"]


class EligibilityRuleCreate(BaseModel):
    field_name: str = Field(min_length=1, max_length=100)
    operator: RuleOperator
    value: str = Field(min_length=1)
    group_id: int | None = None
    logical_operator: LogicalOperator | None = None

    @field_validator("field_name")
    @classmethod
    def validate_profile_field(cls, value: str) -> str:
        from app.models.profile import UserProfile

        if value not in UserProfile.__table__.columns or value in {"id", "user_id"}:
            raise ValueError("field_name must be an eligibility field on UserProfile")
        return value

    @field_validator("value")
    @classmethod
    def require_json_list_for_membership(cls, value: str, info):
        import json

        if info.data.get("operator") in {"in", "not_in"}:
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError("in and not_in values must be JSON arrays") from exc
            if not isinstance(parsed, list) or not parsed:
                raise ValueError("in and not_in values must be non-empty JSON arrays")
        return value

    @model_validator(mode="after")
    def validate_operator_for_field(self):
        from app.models.profile import UserProfile

        column = UserProfile.__table__.columns[self.field_name]
        python_type = column.type.python_type
        numeric_operators = {"lt", "lte", "gt", "gte"}

        if self.operator in numeric_operators and python_type not in {int, float}:
            raise ValueError("numeric operators require a numeric profile field")
        if self.operator == "contains" and python_type is not str:
            raise ValueError("contains requires a text profile field")
        return self


class EligibilityRuleResponse(BaseModel):
    id: int
    scheme_id: int
    field_name: str
    operator: str
    value: str
    group_id: int | None
    logical_operator: str | None

    class Config:
        from_attributes = True


class EligibilityRuleUpdate(EligibilityRuleCreate):
    pass
