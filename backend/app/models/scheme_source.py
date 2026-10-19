from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.database.base import Base


class SchemeSource(Base):
    """Registry of authorized or curated government data sources."""

    __tablename__ = "scheme_sources"
    __table_args__ = (UniqueConstraint("source_name", "source_url", name="uq_scheme_source_name_url"),)

    id = Column(Integer, primary_key=True)
    source_name = Column(String(200), nullable=False)
    source_url = Column(String(1000), nullable=False)
    api_url = Column(String(1000), nullable=True)
    provider = Column(String(300), nullable=True)
    source_type = Column(String(40), nullable=False, default="official_portal", server_default="official_portal")
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    last_checked = Column(DateTime(timezone=True), nullable=True)
    last_successful_sync = Column(DateTime(timezone=True), nullable=True)
    sync_interval_hours = Column(Integer, nullable=False, default=24, server_default="24")
    status = Column(String(30), nullable=False, default="healthy", server_default="healthy")
    error_details = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    schemes = relationship("Scheme", back_populates="source")
    versions = relationship("SchemeVersion", back_populates="source")
    imports = relationship("SchemeImportHistory", back_populates="source")


class SchemeVersion(Base):
    """Immutable scheme-data snapshot; workflow fields record review state."""

    __tablename__ = "scheme_versions"
    __table_args__ = (
        UniqueConstraint("scheme_id", "version_number", name="uq_scheme_version_number"),
        UniqueConstraint("scheme_id", "content_hash", name="uq_scheme_version_hash"),
    )

    id = Column(Integer, primary_key=True)
    scheme_id = Column(Integer, ForeignKey("schemes.id", ondelete="CASCADE"), nullable=False, index=True)
    source_id = Column(Integer, ForeignKey("scheme_sources.id", ondelete="SET NULL"), nullable=True, index=True)
    version_number = Column(Integer, nullable=False)
    snapshot = Column(JSON, nullable=False)
    source_url = Column(String(1000), nullable=True)
    verification_status = Column(String(30), nullable=False, default="pending", server_default="pending")
    eligibility_verification_status = Column(String(30), nullable=False, default="unverified", server_default="unverified")
    verified_at = Column(Date, nullable=True)
    effective_from = Column(Date, nullable=True)
    effective_until = Column(Date, nullable=True)
    imported_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    change_summary = Column(Text, nullable=True)
    content_hash = Column(String(64), nullable=False)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    review_notes = Column(Text, nullable=True)

    scheme = relationship("Scheme", back_populates="versions")
    source = relationship("SchemeSource", back_populates="versions")


class SchemeImportHistory(Base):
    """One durable result row per source processed by an import run."""

    __tablename__ = "scheme_import_history"

    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey("scheme_sources.id", ondelete="SET NULL"), nullable=True, index=True)
    source_name = Column(String(200), nullable=False)
    source_url = Column(String(1000), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(30), nullable=False, default="running", server_default="running")
    discovered = Column(Integer, nullable=False, default=0, server_default="0")
    added = Column(Integer, nullable=False, default=0, server_default="0")
    updated = Column(Integer, nullable=False, default=0, server_default="0")
    unchanged = Column(Integer, nullable=False, default=0, server_default="0")
    skipped = Column(Integer, nullable=False, default=0, server_default="0")
    failed = Column(Integer, nullable=False, default=0, server_default="0")
    details = Column(JSON, nullable=False, default=dict, server_default="{}")
    source = relationship("SchemeSource", back_populates="imports")
