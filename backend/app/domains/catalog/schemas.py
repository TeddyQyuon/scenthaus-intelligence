"""Pydantic v2 schemas for tenant-scoped Product & Variant CRUD."""

from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

ConcentrationType = Literal["EDT", "EDP", "Parfum", "Cologne", "Unverified"]


class NotesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    top: list[str] = Field(default_factory=list, max_length=15)
    heart: list[str] = Field(default_factory=list, max_length=15)
    base: list[str] = Field(default_factory=list, max_length=15)


class VariantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    sku: str = Field(min_length=2, max_length=40)
    size_ml: int = Field(ge=1, le=1000)
    price: Decimal = Field(gt=Decimal("0"), max_digits=10, decimal_places=2)
    stock: int = Field(ge=0, le=100_000)
    lead_time_weeks: int = Field(default=2, ge=0, le=52)


class VariantUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    sku: str | None = Field(default=None, min_length=2, max_length=40)
    price: Decimal | None = Field(
        default=None, gt=Decimal("0"), max_digits=10, decimal_places=2
    )
    stock: int | None = Field(default=None, ge=0, le=100_000)
    lead_time_weeks: int | None = Field(default=None, ge=0, le=52)


class ProductCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=2, max_length=100)
    brand: str = Field(min_length=2, max_length=100)
    slug: str | None = Field(default=None, min_length=2, max_length=100)
    concentration: ConcentrationType = "EDP"
    category: str = Field(default="Woody", min_length=2, max_length=30)
    gender: str = Field(default="Unisex", min_length=2, max_length=20)
    description: str = Field(min_length=10, max_length=1000)
    notes: NotesInput = Field(default_factory=NotesInput)
    accords: dict[str, float] = Field(default_factory=dict)
    seasons: list[str] = Field(default_factory=lambda: ["Autumn", "Winter"])
    occasions: list[str] = Field(default_factory=lambda: ["Everyday"])
    longevity: float = Field(default=6.0, ge=0, le=24)
    sillage: str = Field(default="Moderate", max_length=30)
    launch_date: date = Field(default_factory=date.today)
    pinned: bool = False
    hidden: bool = False
    image_path: str | None = Field(default=None, max_length=500)
    variants: list[VariantCreate] = Field(min_length=1, max_length=10)


class ProductUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str | None = Field(default=None, min_length=2, max_length=100)
    brand: str | None = Field(default=None, min_length=2, max_length=100)
    concentration: ConcentrationType | None = None
    category: str | None = Field(default=None, min_length=2, max_length=30)
    gender: str | None = Field(default=None, min_length=2, max_length=20)
    description: str | None = Field(default=None, min_length=10, max_length=1000)
    notes: NotesInput | None = None
    accords: dict[str, float] | None = None
    seasons: list[str] | None = None
    occasions: list[str] | None = None
    longevity: float | None = Field(default=None, ge=0, le=24)
    sillage: str | None = Field(default=None, max_length=30)
    pinned: bool | None = None
    hidden: bool | None = None
    image_path: str | None = Field(default=None, max_length=500)
