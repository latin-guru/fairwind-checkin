"""Server-side validation of the check-in form (Pydantic v2)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

AgeRange = Literal["18-24", "25-34", "35-44", "45-54", "55-64", "65+"]
TripType = Literal["beach", "cruise", "europe", "adventure", "family", "honeymoon", "group_event"]
PartySize = Literal["1", "2", "3-4", "5-8", "9+"]
BudgetBand = Literal["under_2k", "2k_5k", "5k_10k", "10k_plus"]
Source = Literal["instagram", "facebook", "google", "referral", "event", "other"]


class CheckIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    first_name: str = Field(min_length=1, max_length=60)
    last_name: str = Field(min_length=1, max_length=60)
    email: EmailStr
    zip: str = Field(pattern=r"^\d{5}$")
    age_range: AgeRange
    trip_type: TripType
    party_size: PartySize
    budget_band: BudgetBand
    source: Source
    # Unchecked by default. An unticked HTML checkbox sends nothing, so a missing value means "no".
    marketing_consent: bool = False

    @field_validator("email")
    @classmethod
    def lower_email(cls, v: str) -> str:
        return v.lower()

    @field_validator("first_name", "last_name")
    @classmethod
    def no_markup(cls, v: str) -> str:
        if any(c in v for c in "<>{}"):
            raise ValueError("Please use letters only.")
        return v


FRIENDLY = {
    "first_name": "Please enter your first name.",
    "last_name": "Please enter your last name.",
    "email": "Please enter a valid email address.",
    "zip": "Please enter a 5-digit zip code.",
    "age_range": "Please choose an age range.",
    "trip_type": "Please choose a trip type.",
    "party_size": "Please choose your party size.",
    "budget_band": "Please choose a budget.",
    "source": "Please tell us how you heard about us.",
}


def errors_by_field(exc) -> dict[str, str]:
    out = {}
    for err in exc.errors():
        field = str(err["loc"][0]) if err.get("loc") else "form"
        out.setdefault(field, FRIENDLY.get(field, "Please check this field."))
    return out
