from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.retrieval import SchemeSearchResponse
from app.services.retrieval import search_schemes


router = APIRouter(prefix="/api/schemes", tags=["Scheme retrieval"])


@router.get("/search", response_model=SchemeSearchResponse)
def retrieve_schemes(
    q: str = Query(default="", max_length=500),
    category: str | None = Query(default=None, max_length=100),
    beneficiary_group: str | None = Query(default=None, max_length=150),
    state: str | None = Query(default=None, max_length=100),
    active_only: bool = True,
    limit: int = Query(default=10, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return SchemeSearchResponse(
        query=q,
        results=search_schemes(
            db, q, category=category, beneficiary_group=beneficiary_group,
            state=state, active_only=active_only, limit=limit,
        ),
    )
