"""Tenant-scoped Customers routes (merchant admin)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DatabaseSession

from ...database import get_db
from ...models import Tenant, User
from ...tenancy.deps import require_tenant_role
from .service import get_tenant_customer, list_tenant_customers

router = APIRouter(prefix="/tenant/customers", tags=["tenant-customers"])


@router.get("", include_in_schema=True)
@router.get("/", include_in_schema=False)
def list_customers(
    include_simulated: bool = Query(default=False),
    ctx: tuple[Tenant, User] = Depends(
        require_tenant_role("owner", "admin", "manager", "analyst")
    ),
    db: DatabaseSession = Depends(get_db),
):
    """List tenant customers with order counts and total spend."""
    tenant, _ = ctx
    return {
        "tenant_id": tenant.id,
        "customers": list_tenant_customers(
            db, tenant, include_simulated=include_simulated
        ),
    }


@router.get("/{customer_id}")
def get_customer(
    customer_id: str,
    include_simulated: bool = Query(default=False),
    ctx: tuple[Tenant, User] = Depends(
        require_tenant_role("owner", "admin", "manager", "analyst")
    ),
    db: DatabaseSession = Depends(get_db),
):
    """Get customer profile and their order history in this tenant."""
    tenant, _ = ctx
    return get_tenant_customer(
        db, tenant, customer_id, include_simulated=include_simulated
    )
