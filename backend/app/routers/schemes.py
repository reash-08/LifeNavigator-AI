from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.database.connection import get_db
from app.core.security import get_current_admin
from app.models.scheme import Scheme
from app.models.scheme_source import SchemeSource
from app.schemas.scheme import SchemeCreate, SchemeResponse
from app.services.scheme_sync import is_official_source_url
from app.services.slug_generator import generate_base_slug, resolve_slug_collision


router = APIRouter(
    prefix="/api/schemes",
    tags=["Schemes"],
)


@router.post(
    "",
    response_model=SchemeResponse,
    status_code=status.HTTP_201_CREATED
)
def create_scheme(
    scheme_data: SchemeCreate,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    dump = scheme_data.model_dump()
    requested_slug = dump.get("slug")
    if not requested_slug:
        jurisdiction = (dump.get("state") or "CENTRAL").upper()
        existing_slugs = {
            s[0] for s in db.query(Scheme.slug).filter(
                Scheme.is_active.is_(True),
                func.coalesce(Scheme.state, "CENTRAL") == (dump.get("state") or "CENTRAL")
            ).all() if s[0]
        }
        base = generate_base_slug(dump["name"])
        dump["slug"] = resolve_slug_collision(
            base,
            existing_slugs,
            name=dump["name"],
            jurisdiction=jurisdiction,
            ministry=dump.get("ministry"),
        )
    scheme = Scheme(**dump)

    if scheme.source_name and scheme.source_url and is_official_source_url(scheme.source_url):
        source = db.query(SchemeSource).filter_by(source_name=scheme.source_name, source_url=scheme.source_url).first()
        if source is None:
            source = SchemeSource(
                source_name=scheme.source_name,
                source_url=scheme.source_url,
                provider=scheme.ministry,
                source_type="official_portal",
                is_active=True,
                notes="Registered from an administrator-created scheme record.",
            )
            db.add(source)
            db.flush()
        scheme.source_id = source.id

    try:
        db.add(scheme)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A scheme with this identifier already exists in this jurisdiction. Refresh the list and try again.",
        )
    db.refresh(scheme)

    return scheme


@router.get(
    "",
    response_model=list[SchemeResponse]
)
def get_schemes(
    db: Session = Depends(get_db),
):
    return db.query(Scheme).options(selectinload(Scheme.eligibility_rules)).all()


@router.get(
    "/{scheme_id}",
    response_model=SchemeResponse
)
def get_scheme(
    scheme_id: int,
    db: Session = Depends(get_db),
):
    scheme = (
        db.query(Scheme)
        .options(selectinload(Scheme.eligibility_rules))
        .filter(Scheme.id == scheme_id)
        .first()
    )

    if not scheme:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scheme not found",
        )

    return scheme


@router.put(
    "/{scheme_id}",
    response_model=SchemeResponse
)
def update_scheme(
    scheme_id: int,
    scheme_data: SchemeCreate,
    _: object = Depends(get_current_admin),
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

    for field, value in scheme_data.model_dump().items():
        setattr(scheme, field, value)

    db.commit()
    db.refresh(scheme)

    return scheme


@router.delete(
    "/{scheme_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_scheme(
    scheme_id: int,
    _: object = Depends(get_current_admin),
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

    db.delete(scheme)
    db.commit()

    return None
