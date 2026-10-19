from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database.connection import get_db
from app.models.profile import UserProfile
from app.models.scheme import Scheme
from app.models.user import User
from app.schemas.eligibility import EligibleSchemeResponse
from app.services.eligibility import check_scheme_eligibility


router = APIRouter(
    prefix="/api/eligibility",
    tags=["Eligibility"],
)


@router.get(
    "/matches",
    response_model=list[EligibleSchemeResponse],
)
def get_eligible_schemes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = (
        db.query(UserProfile)
        .filter(UserProfile.user_id == current_user.id)
        .first()
    )

    if not profile:
        return []

    schemes = (
        db.query(Scheme)
        .filter(Scheme.is_active == True)
        .all()
    )

    results = []

    for scheme in schemes:

        assessment = check_scheme_eligibility(
            profile,
            scheme
        )

        results.append(
            EligibleSchemeResponse(
                id=scheme.id,
                name=scheme.name,
                description=scheme.description,
                state=scheme.state,
                government_level=scheme.government_level,
                ministry=scheme.ministry,
                department=scheme.department,
                beneficiary_groups=scheme.beneficiary_groups,
                source_url=scheme.source_url,
                source_name=scheme.source_name,
                verified_at=scheme.verified_at,
                verification_status=scheme.verification_status,
                eligibility_verification_status=scheme.eligibility_verification_status,
                min_age=scheme.min_age,
                max_age=scheme.max_age,
                education=scheme.education,
                employment_status=scheme.employment_status,
                category=scheme.category,
                subcategory=scheme.subcategory,
                max_annual_income=scheme.max_annual_income,
                benefit=scheme.benefit,
                required_documents=scheme.required_documents,
                application_process=scheme.application_process,
                application_url=scheme.application_url,
                application_deadline=scheme.application_deadline,
                is_active=scheme.is_active,
                eligible=assessment.eligible,
                reasons=assessment.reasons,
                assessment_status=assessment.status,
                missing_fields=assessment.missing_fields,
            )
        )

    return results
