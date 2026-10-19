"""Pydantic v2 schemas for tenant-scoped Customers."""

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class CustomerSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    email: str | None = None
    role: str
    consent: bool
    created_at: str | None = None
    order_count: int = 0
    total_spend: float = 0.0


class CustomerOrderSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    order_number: str | None = None
    status: str
    payment_status: str | None = None
    total: float
    total_minor: int | None = None
    currency: str | None = None
    customer_name: str | None = None
    customer_email: str | None = None
    delivery_address: dict[str, Any] | None = None
    created_at: str | None = None
    paid_at: str | None = None


class CustomerProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    email: str | None = None
    role: str
    consent: bool
    created_at: str | None = None
    order_count: int = 0
    total_spend: float = 0.0


class CustomerDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    email: str | None = None
    role: str
    consent: bool
    created_at: str | None = None
    order_count: int = 0
    total_spend: float = 0.0
    orders: list[CustomerOrderSummary] = Field(default_factory=list)
    customer: CustomerProfile | None = None
