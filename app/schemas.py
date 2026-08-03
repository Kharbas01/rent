"""Pydantic models used for request validation."""

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

PropertyStatus = Literal["Occupied", "Vacant"]
PaymentMethod = Literal["Cash", "Bank Transfer", "UPI", "Card", "Cheque", "Other"]
PaymentType = Literal["Cash", "Online", "Hybrid"]


def _clean(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value or None


def add_months(source_date: date, months: int) -> date:
    """Add a number of months to a date, clamping the day to the target month's length.

    Used by the rent-increase auto-apply logic in app/crud.py to compute the
    next increase date from an agreement's start date and cycle length.
    """
    import calendar

    month_index = source_date.month - 1 + months
    year = source_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(source_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------
class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class SignupIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class PasswordIn(BaseModel):
    new_password: str = Field(min_length=6, max_length=128)


# --------------------------------------------------------------------------
# Profile
# --------------------------------------------------------------------------
class ProfileIn(BaseModel):
    full_name: Optional[str] = Field(default=None, max_length=120)
    company_name: Optional[str] = Field(default=None, max_length=120)
    phone: Optional[str] = Field(default=None, max_length=30)
    currency: str = Field(default="INR", max_length=8)

    @field_validator("full_name", "company_name", "phone", mode="before")
    @classmethod
    def _strip(cls, value):
        return _clean(value) if isinstance(value, str) else value


# --------------------------------------------------------------------------
# Property
# --------------------------------------------------------------------------
class PropertyIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    type: str = Field(default="Apartment", max_length=60)
    address: Optional[str] = Field(default=None, max_length=400)
    monthly_rent: float = Field(default=0, ge=0, le=99_999_999)
    status: PropertyStatus = "Vacant"
    notes: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("name", "type", mode="before")
    @classmethod
    def _required_strip(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("address", "notes", mode="before")
    @classmethod
    def _optional_strip(cls, value):
        return _clean(value) if isinstance(value, str) else value


# --------------------------------------------------------------------------
# Tenant
# --------------------------------------------------------------------------
class TenantIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: Optional[str] = Field(default=None, max_length=30)
    email: Optional[EmailStr] = None
    property_id: Optional[str] = None
    rent_amount: float = Field(default=0, ge=0, le=99_999_999)
    security_deposit: float = Field(default=0, ge=0, le=99_999_999)
    agreement_start: Optional[date] = None
    agreement_end: Optional[date] = None
    due_day_of_month: int = Field(default=1, ge=1, le=31)
    agreement_duration_months: Optional[int] = Field(default=None, ge=1, le=600)
    rent_increase_percentage: float = Field(default=0, ge=0, le=100)
    is_active: bool = True
    notes: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("name", mode="before")
    @classmethod
    def _required_strip(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("phone", "notes", "property_id", "email", mode="before")
    @classmethod
    def _optional_strip(cls, value):
        return _clean(value) if isinstance(value, str) else value

    @field_validator("agreement_end")
    @classmethod
    def _check_dates(cls, value, info):
        start = info.data.get("agreement_start")
        if value and start and value < start:
            raise ValueError("Agreement end date must be after the start date.")
        return value

    @field_validator("agreement_duration_months")
    @classmethod
    def _check_duration(cls, value, info):
        """If both dates and a duration are given, they must roughly agree."""
        if value is None:
            return value
        start = info.data.get("agreement_start")
        end = info.data.get("agreement_end")
        if start and end:
            months = (end.year - start.year) * 12 + (end.month - start.month)
            # Allow a 1-month tolerance for partial/odd-day months.
            if abs(months - value) > 1:
                raise ValueError(
                    "Agreement duration (months) does not match the start/end dates."
                )
        return value


# --------------------------------------------------------------------------
# Payments
# --------------------------------------------------------------------------
class PaymentIn(BaseModel):
    tenant_id: str = Field(min_length=1)
    period_month: str = Field(pattern=r"^\d{4}-\d{2}$")
    amount_due: float = Field(ge=0, le=99_999_999)
    amount_paid: float = Field(default=0, ge=0, le=99_999_999)
    payment_date: Optional[date] = None
    payment_method: Optional[PaymentMethod] = None
    payment_type: PaymentType = "Cash"
    payment_type_note: Optional[str] = Field(default=None, max_length=300)
    notes: Optional[str] = Field(default=None, max_length=500)

    @field_validator("notes", "payment_type_note", mode="before")
    @classmethod
    def _optional_strip(cls, value):
        return _clean(value) if isinstance(value, str) else value

    @field_validator("payment_type_note")
    @classmethod
    def _require_note_for_hybrid(cls, value, info):
        payment_type = info.data.get("payment_type")
        if payment_type == "Hybrid" and not value:
            raise ValueError(
                "Please add a breakdown note for a hybrid payment (e.g. '₹5,000 Cash + ₹10,000 UPI')."
            )
        return value


class MarkPaidIn(BaseModel):
    amount_paid: float = Field(ge=0, le=99_999_999)
    payment_date: date
    payment_method: PaymentMethod = "Cash"
    payment_type: PaymentType = "Cash"
    payment_type_note: Optional[str] = Field(default=None, max_length=300)
    notes: Optional[str] = Field(default=None, max_length=500)

    @field_validator("notes", "payment_type_note", mode="before")
    @classmethod
    def _optional_strip(cls, value):
        return _clean(value) if isinstance(value, str) else value

    @field_validator("payment_type_note")
    @classmethod
    def _require_note_for_hybrid(cls, value, info):
        payment_type = info.data.get("payment_type")
        if payment_type == "Hybrid" and not value:
            raise ValueError(
                "Please add a breakdown note for a hybrid payment (e.g. '₹5,000 Cash + ₹10,000 UPI')."
            )
        return value


class GenerateIn(BaseModel):
    period_month: str = Field(pattern=r"^\d{4}-\d{2}$")


# --------------------------------------------------------------------------
# Agreements (metadata only — the file itself is handled as multipart form
# data in the router, not through this JSON body)
# --------------------------------------------------------------------------
class AgreementMetaIn(BaseModel):
    property_id: Optional[str] = None
    tenant_id: Optional[str] = None
    agreement_start: Optional[date] = None
    agreement_end: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("property_id", "tenant_id", "notes", mode="before")
    @classmethod
    def _optional_strip(cls, value):
        return _clean(value) if isinstance(value, str) else value

    @field_validator("agreement_end")
    @classmethod
    def _check_dates(cls, value, info):
        start = info.data.get("agreement_start")
        if value and start and value < start:
            raise ValueError("Agreement end date must be after the start date.")
        return value