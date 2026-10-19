from sqlalchemy import Boolean, Column, Date, ForeignKey, Integer, String, Text, JSON, event
from sqlalchemy.orm import relationship

from app.database.base import Base


class Scheme(Base):
    __tablename__ = "schemes"

    def __init__(self, **kwargs):
        if not kwargs.get("slug") and kwargs.get("name"):
            from app.services.slug_generator import generate_base_slug
            kwargs["slug"] = generate_base_slug(kwargs["name"])
        super().__init__(**kwargs)

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)

    # Geographic reach and public classification. Existing ``state`` remains a
    # legacy location criterion; ``government_level`` describes scheme ownership.
    state = Column(String(100), nullable=True)
    government_level = Column(String(30), nullable=True)  # central/state/ut/local
    ministry = Column(String(200), nullable=True)
    department = Column(String(200), nullable=True)
    beneficiary_groups = Column(JSON, nullable=True)
    source_url = Column(String(500), nullable=True)
    source_name = Column(String(200), nullable=True)
    verified_at = Column(Date, nullable=True)
    verification_status = Column(String(30), nullable=True)  # unverified/verified/review_needed
    eligibility_verification_status = Column(String(30), nullable=False, default="unverified", server_default="unverified")
    source_id = Column(Integer, ForeignKey("scheme_sources.id", ondelete="SET NULL"), nullable=True, index=True)

    min_age = Column(Integer, nullable=True)
    max_age = Column(Integer, nullable=True)

    education = Column(String(100), nullable=True)
    employment_status = Column(String(100), nullable=True)
    category = Column(String(100), nullable=True)
    subcategory = Column(String(100), nullable=True)

    max_annual_income = Column(Integer, nullable=True)

    benefit = Column(Text, nullable=False)
    required_documents = Column(Text, nullable=True)
    application_process = Column(Text, nullable=True)

    application_url = Column(String(500), nullable=True)
    application_deadline = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Stage 3C Identity & Deduplication fields
    slug = Column(String(80), nullable=False, index=True)
    aliases = Column(JSON, nullable=False, default=list)
    canonical_scheme_id = Column(Integer, ForeignKey("schemes.id", ondelete="RESTRICT"), nullable=True)
    canonical_scheme = relationship("Scheme", remote_side=[id], backref="redirected_schemes")

    eligibility_rules = relationship(
        "EligibilityRule",
        back_populates="scheme",
        cascade="all, delete-orphan"
    )
    @property
    def effective_eligibility_rules(self):
        return [rule for rule in self.eligibility_rules if rule.is_active]

    versions = relationship("SchemeVersion", back_populates="scheme", cascade="all, delete-orphan", order_by="SchemeVersion.version_number")
    source = relationship("SchemeSource", back_populates="schemes")
    documents = relationship("SchemeDocument", back_populates="scheme", cascade="all, delete-orphan")


@event.listens_for(Scheme, "before_insert")
def _auto_populate_scheme_slug_before_insert(mapper, connection, target):
    if not target.slug and target.name:
        from app.services.slug_generator import generate_base_slug
        target.slug = generate_base_slug(target.name)


@event.listens_for(Scheme, "before_update")
def _auto_populate_scheme_slug_before_update(mapper, connection, target):
    if not target.slug and target.name:
        from app.services.slug_generator import generate_base_slug
        target.slug = generate_base_slug(target.name)

