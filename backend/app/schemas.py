from typing import Literal
from pydantic import BaseModel, Field, field_validator


class Credentials(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=10, max_length=128)
    otp_code: str | None = Field(default=None, max_length=40)

    @field_validator("email")
    @classmethod
    def email_check(cls, value):
        value = value.strip().lower()
        if "@" not in value or "." not in value.split("@")[-1]:
            raise ValueError("Valid email required")
        return value


class Consent(BaseModel):
    consent: bool


class CartUpdate(BaseModel):
    variant_id: int
    quantity: int = Field(ge=1, le=10)


class Checkout(BaseModel):
    idempotency_key: str = Field(
        min_length=16, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$"
    )


class Quiz(BaseModel):
    mood: Literal["fresh", "warm", "floral", "woody"]
    occasion: Literal["office", "everyday", "evening", "gift"]
    intensity: Literal["soft", "balanced", "bold"]
    budget: float = Field(ge=30, le=600)
    size: int | None = None

    @field_validator("size")
    @classmethod
    def sizes(cls, v):
        if v not in [None, 30, 50, 100]:
            raise ValueError("Choose 30, 50 or 100ml")
        return v


class TrackedEvent(BaseModel):
    product_id: int
    event_type: Literal["view", "impression", "click"]
    recommendation_id: str | None = None


class Override(BaseModel):
    pinned: bool = False
    hidden: bool = False


class Stock(BaseModel):
    stock: int = Field(ge=0, le=100000)


class Experiment(BaseModel):
    visitors: int = Field(default=10000, ge=100, le=200000)
    baseline_rate: float = Field(default=0.04, gt=0, lt=0.5)
    relative_lift: float = Field(default=0.1, ge=-0.9, le=1)
    seed: int = 42
