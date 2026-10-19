from sqlalchemy import Boolean, Column, Float, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from app.database.base import Base


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        unique=True
    )

    # =========================
    # PERSONAL INFORMATION
    # =========================
    full_name = Column(String(100), nullable=False)
    age = Column(Integer, nullable=False)
    gender = Column(String(20), nullable=False)
    marital_status = Column(String(30), nullable=True)

    # =========================
    # LOCATION
    # =========================
    state = Column(String(100), nullable=False)
    district = Column(String(100), nullable=True)
    pincode = Column(String(10), nullable=True)
    domicile_state = Column(String(100), nullable=True)
    rural_or_urban = Column(String(20), nullable=True)

    # =========================
    # SOCIAL / CATEGORY
    # =========================
    category = Column(String(50), nullable=True)
    minority_status = Column(Boolean, nullable=True)

    # =========================
    # EDUCATION
    # =========================
    education = Column(String(100), nullable=True)
    course = Column(String(150), nullable=True)
    specialization = Column(String(150), nullable=True)
    institution_type = Column(String(100), nullable=True)
    year_of_study = Column(Integer, nullable=True)
    previous_qualification = Column(String(150), nullable=True)
    marks_percentage = Column(Float, nullable=True)

    # =========================
    # EMPLOYMENT
    # =========================
    employment_status = Column(String(100), nullable=True)
    occupation = Column(String(150), nullable=True)
    beneficiary_group = Column(String(100), nullable=True)
    fisher_activity = Column(String(100), nullable=True)
    employment_type = Column(String(100), nullable=True)
    sector = Column(String(100), nullable=True)

    # =========================
    # FINANCIAL INFORMATION
    # =========================
    annual_income = Column(Integer, nullable=True)
    income_source = Column(String(100), nullable=True)
    income_certificate_available = Column(Boolean, nullable=True)
    bpl_status = Column(Boolean, nullable=True)
    ration_card_type = Column(String(100), nullable=True)

    # =========================
    # FAMILY INFORMATION
    # =========================
    family_size = Column(Integer, nullable=True)
    dependents = Column(Integer, nullable=True)
    parents_alive = Column(Boolean, nullable=True)
    single_parent = Column(Boolean, nullable=True)
    orphan = Column(Boolean, nullable=True)

    # =========================
    # DISABILITY INFORMATION
    # =========================
    has_disability = Column(Boolean, nullable=True)
    disability_type = Column(String(100), nullable=True)
    disability_percentage = Column(Float, nullable=True)
    disability_certificate_available = Column(Boolean, nullable=True)

    # =========================
    # AGRICULTURE INFORMATION
    # =========================
    is_farmer = Column(Boolean, nullable=True)
    land_ownership = Column(Boolean, nullable=True)
    land_area = Column(Float, nullable=True)
    land_unit = Column(String(30), nullable=True)
    crop_type = Column(String(150), nullable=True)
    irrigation_available = Column(Boolean, nullable=True)

    # =========================
    # HOUSING INFORMATION
    # =========================
    owns_house = Column(Boolean, nullable=True)
    house_type = Column(String(100), nullable=True)
    housing_condition = Column(String(100), nullable=True)
    electricity_available = Column(Boolean, nullable=True)
    toilet_available = Column(Boolean, nullable=True)

    # =========================
    # SPECIAL CIRCUMSTANCES
    # =========================
    widow = Column(Boolean, nullable=True)
    ex_serviceman_family = Column(Boolean, nullable=True)
    senior_citizen = Column(Boolean, nullable=True)

    # =========================
    # RELATIONSHIP
    # =========================
    user = relationship("User", back_populates="profile")