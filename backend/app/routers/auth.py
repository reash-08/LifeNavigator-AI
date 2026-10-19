from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limit import limiter, get_client_ip
from app.core.security import get_current_user
from app.database.connection import SessionLocal
from app.models.user import User
from app.schemas.auth import UserRegister, UserResponse, UserLogin, TokenResponse, PasswordChange
from app.services.auth_service import hash_password, verify_password
from app.services.jwt_service import create_access_token

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"]
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED
)
@limiter.limit(lambda: settings.RATE_LIMIT_REGISTER, key_func=get_client_ip)
def register_user(
    request: Request,
    user_data: UserRegister,
    db: Session = Depends(get_db)
):
    existing_user = db.scalar(
        select(User).where(User.email == str(user_data.email).casefold())
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered"
        )

    email = str(user_data.email).casefold()
    new_user = User(
        email=email,
        password_hash=hash_password(user_data.password),
        is_admin=email in settings.admin_emails,
    )

    try:
        db.add(new_user)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered",
        )
    db.refresh(new_user)

    return new_user


@router.post(
    "/login",
    response_model=TokenResponse
)
@limiter.limit(lambda: settings.RATE_LIMIT_LOGIN, key_func=get_client_ip)
def login_user(
    request: Request,
    user_data: UserLogin,
    db: Session = Depends(get_db)
):
    user = db.scalar(
        select(User).where(User.email == str(user_data.email).casefold())
    )

    if not user or not verify_password(
        user_data.password,
        user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    access_token = create_access_token(user.id)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    account = db.get(User, current_user.id)
    if account is None or not verify_password(password_data.current_password, account.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    account.password_hash = hash_password(password_data.new_password)
    db.commit()
    return None
