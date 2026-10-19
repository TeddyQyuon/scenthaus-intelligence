"""Tenant-scoped Customers domain module following the standard pattern: schemas -> service -> router."""

from .router import router

__all__ = ["router"]
