"""Reference tenant-scoped Catalog CRUD module (template for all domain modules).

Structure:
- schemas.py: Strict Pydantic v2 request/response models (`extra="forbid"`)
- service.py: Tenant-isolated business logic & audit logging
- router.py: FastAPI routes using `resolve_tenant` / `require_tenant_role`
"""

from .router import router

__all__ = ["router"]
