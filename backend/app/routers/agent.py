from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limit import limiter, get_user_or_ip
from app.core.security import get_current_user
from app.database.connection import get_db
from app.models.profile import UserProfile
from app.models.user import User
from app.schemas.agent import AgentQuery, AgentResponse
from app.services.agent import run_agent

router = APIRouter(prefix="/api/agent", tags=["Agent"])


@router.post("/query", response_model=AgentResponse)
@limiter.limit(lambda: settings.RATE_LIMIT_AGENT, key_func=get_user_or_ip)
def query_agent(
    request: Request,
    payload: AgentQuery,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    return run_agent(db, query=payload.query, profile=profile)
