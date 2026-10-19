from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database.base import Base


class EligibilityRule(Base):
    __tablename__ = "eligibility_rules"

    id = Column(Integer, primary_key=True, index=True)

    scheme_id = Column(
        Integer,
        ForeignKey("schemes.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Profile field to check
    field_name = Column(
        String(100),
        nullable=False
    )

    # Comparison operator
    operator = Column(
        String(20),
        nullable=False
    )

    # Value used for comparison
    value = Column(
        Text,
        nullable=False
    )

    # Used for grouping AND / OR conditions
    group_id = Column(
        Integer,
        nullable=True
    )

    logical_operator = Column(
        String(10),
        nullable=True
    )

    scheme = relationship(
        "Scheme",
        back_populates="eligibility_rules",
    )
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    source_version_id = Column(Integer, ForeignKey("scheme_versions.id", ondelete="SET NULL"), nullable=True, index=True)
