from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.core.security import get_current_admin
from app.models.eligibility_rule import EligibilityRule
from app.models.scheme import Scheme
from app.schemas.eligibility_rule import (
    EligibilityRuleCreate,
    EligibilityRuleResponse,
    EligibilityRuleUpdate,
)


router = APIRouter(
    prefix="/api/schemes/{scheme_id}/rules",
    tags=["Eligibility Rules"],
    dependencies=[Depends(get_current_admin)],
)


@router.post(
    "",
    response_model=EligibilityRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_rule(
    scheme_id: int,
    rule_data: EligibilityRuleCreate,
    db: Session = Depends(get_db),
):
    scheme = (
        db.query(Scheme)
        .filter(Scheme.id == scheme_id)
        .first()
    )

    if not scheme:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scheme not found",
        )

    rule = EligibilityRule(
        scheme_id=scheme_id,
        **rule_data.model_dump(),
    )

    db.add(rule)
    db.commit()
    db.refresh(rule)

    return rule


@router.get(
    "",
    response_model=list[EligibilityRuleResponse],
)
def get_rules(
    scheme_id: int,
    db: Session = Depends(get_db),
):
    scheme = (
        db.query(Scheme)
        .filter(Scheme.id == scheme_id)
        .first()
    )

    if not scheme:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scheme not found",
        )

    return (
        db.query(EligibilityRule)
        .filter(EligibilityRule.scheme_id == scheme_id, EligibilityRule.is_active.is_(True))
        .all()
    )


@router.put(
    "/{rule_id}",
    response_model=EligibilityRuleResponse,
)
def update_rule(
    scheme_id: int,
    rule_id: int,
    rule_data: EligibilityRuleUpdate,
    db: Session = Depends(get_db),
):
    rule = (
        db.query(EligibilityRule)
        .filter(
            EligibilityRule.id == rule_id,
            EligibilityRule.scheme_id == scheme_id,
        )
        .first()
    )

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Eligibility rule not found",
        )

    for field, value in rule_data.model_dump().items():
        setattr(rule, field, value)

    db.commit()
    db.refresh(rule)
    return rule


@router.delete(
    "/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_rule(
    scheme_id: int,
    rule_id: int,
    db: Session = Depends(get_db),
):
    rule = (
        db.query(EligibilityRule)
        .filter(
            EligibilityRule.id == rule_id,
            EligibilityRule.scheme_id == scheme_id,
        )
        .first()
    )

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Eligibility rule not found",
        )

    db.delete(rule)
    db.commit()

    return None
