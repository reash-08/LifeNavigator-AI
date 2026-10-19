from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database.connection import get_db
from app.models.profile import UserProfile
from app.models.user import User
from app.schemas.profile import ProfileCreate, ProfileResponse


router = APIRouter(
    prefix="/api/profile",
    tags=["Profile"],
)


@router.post(
    "",
    response_model=ProfileResponse,
    status_code=status.HTTP_201_CREATED
)
def create_profile(
    profile_data: ProfileCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing_profile = (
        db.query(UserProfile)
        .filter(UserProfile.user_id == current_user.id)
        .first()
    )

    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile already exists",
        )

    profile = UserProfile(
        user_id=current_user.id,
        **profile_data.model_dump(),
    )

    db.add(profile)
    db.commit()
    db.refresh(profile)

    return profile


@router.get(
    "",
    response_model=ProfileResponse
)
def get_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = (
        db.query(UserProfile)
        .filter(UserProfile.user_id == current_user.id)
        .first()
    )

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )

    return profile


@router.put(
    "",
    response_model=ProfileResponse
)
def update_profile(
    profile_data: ProfileCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = (
        db.query(UserProfile)
        .filter(UserProfile.user_id == current_user.id)
        .first()
    )

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )

    for field, value in profile_data.model_dump().items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)

    return profile