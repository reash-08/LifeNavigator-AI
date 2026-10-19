from pydantic import BaseModel, Field


class ProfileCreate(BaseModel):

    # =========================
    # PERSONAL INFORMATION
    # =========================
    full_name: str = Field(min_length=2, max_length=100)
    age: int = Field(ge=1, le=120)
    gender: str = Field(min_length=1, max_length=20)
    marital_status: str | None = Field(default=None, max_length=30)

    # =========================
    # LOCATION
    # =========================
    state: str = Field(min_length=1, max_length=100)
    district: str | None = Field(default=None, max_length=100)
    pincode: str | None = Field(default=None, min_length=6, max_length=10)
    domicile_state: str | None = Field(default=None, max_length=100)
    rural_or_urban: str | None = Field(default=None, max_length=20)

    # =========================
    # SOCIAL / CATEGORY
    # =========================
    category: str | None = Field(default=None, max_length=50)
    minority_status: bool | None = None

    # =========================
    # EDUCATION
    # =========================
    education: str | None = Field(default=None, max_length=100)
    course: str | None = Field(default=None, max_length=150)
    specialization: str | None = Field(default=None, max_length=150)
    institution_type: str | None = Field(default=None, max_length=100)
    year_of_study: int | None = Field(default=None, ge=1, le=20)
    previous_qualification: str | None = Field(default=None, max_length=150)
    marks_percentage: float | None = Field(
        default=None,
        ge=0,
        le=100
    )

    # =========================
    # EMPLOYMENT
    # =========================
    employment_status: str | None = Field(default=None, max_length=100)
    occupation: str | None = Field(default=None, max_length=150)
    beneficiary_group: str | None = Field(default=None, max_length=100)
    fisher_activity: str | None = Field(default=None, max_length=100)
    employment_type: str | None = Field(default=None, max_length=100)
    sector: str | None = Field(default=None, max_length=100)

    # =========================
    # FINANCIAL
    # =========================
    annual_income: int | None = Field(default=None, ge=0)
    income_source: str | None = Field(default=None, max_length=100)
    income_certificate_available: bool | None = None
    bpl_status: bool | None = None
    ration_card_type: str | None = Field(default=None, max_length=100)

    # =========================
    # FAMILY
    # =========================
    family_size: int | None = Field(default=None, ge=1)
    dependents: int | None = Field(default=None, ge=0)
    parents_alive: bool | None = None
    single_parent: bool | None = None
    orphan: bool | None = None

    # =========================
    # DISABILITY
    # =========================
    has_disability: bool | None = None
    disability_type: str | None = Field(default=None, max_length=100)
    disability_percentage: float | None = Field(
        default=None,
        ge=0,
        le=100
    )
    disability_certificate_available: bool | None = None

    # =========================
    # AGRICULTURE
    # =========================
    is_farmer: bool | None = None
    land_ownership: bool | None = None
    land_area: float | None = Field(default=None, ge=0)
    land_unit: str | None = Field(default=None, max_length=30)
    crop_type: str | None = Field(default=None, max_length=150)
    irrigation_available: bool | None = None

    # =========================
    # HOUSING
    # =========================
    owns_house: bool | None = None
    house_type: str | None = Field(default=None, max_length=100)
    housing_condition: str | None = Field(default=None, max_length=100)
    electricity_available: bool | None = None
    toilet_available: bool | None = None

    # =========================
    # SPECIAL CIRCUMSTANCES
    # =========================
    widow: bool | None = None
    ex_serviceman_family: bool | None = None
    senior_citizen: bool | None = None


class ProfileResponse(ProfileCreate):
    id: int
    user_id: int

    class Config:
        from_attributes = True