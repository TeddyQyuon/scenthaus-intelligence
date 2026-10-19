"""Tenant-scoped Catalog CRUD routes (storefront + merchant admin)."""

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session as DatabaseSession

from ...database import get_db
from ...models import Tenant, User
from ...tenancy.deps import require_tenant_role, resolve_tenant
from .schemas import ProductCreate, ProductUpdate, VariantCreate, VariantUpdate
from .service import (
    add_or_update_variant,
    create_tenant_product,
    export_tenant_catalog_csv,
    import_tenant_catalog_csv,
    list_tenant_products,
    update_tenant_product,
)

class CSVImportRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    csv_text: str

router = APIRouter(prefix="/tenant/catalog", tags=["tenant-catalog"])


@router.get("/products")
def get_store_products(
    include_hidden: bool = Query(default=False),
    tenant: Tenant = Depends(resolve_tenant),
    db: DatabaseSession = Depends(get_db),
):
    """List products belonging strictly to the resolved tenant."""
    return {
        "tenant_id": tenant.id,
        "products": list_tenant_products(db, tenant, include_hidden=include_hidden),
    }


@router.post("/products", status_code=201)
def create_product(
    body: ProductCreate,
    ctx: tuple[Tenant, User] = Depends(
        require_tenant_role("owner", "admin", "manager")
    ),
    db: DatabaseSession = Depends(get_db),
):
    tenant, user = ctx
    return create_tenant_product(db, tenant, user.id, body)


@router.put("/products/{product_id}")
def update_product(
    product_id: int,
    body: ProductUpdate,
    ctx: tuple[Tenant, User] = Depends(
        require_tenant_role("owner", "admin", "manager")
    ),
    db: DatabaseSession = Depends(get_db),
):
    tenant, user = ctx
    return update_tenant_product(db, tenant, user.id, product_id, body)


@router.post("/products/{product_id}/variants", status_code=201)
def create_variant(
    product_id: int,
    body: VariantCreate,
    ctx: tuple[Tenant, User] = Depends(
        require_tenant_role("owner", "admin", "manager")
    ),
    db: DatabaseSession = Depends(get_db),
):
    tenant, user = ctx
    return add_or_update_variant(db, tenant, user.id, product_id, None, body)


@router.put("/products/{product_id}/variants/{variant_id}")
def update_variant(
    product_id: int,
    variant_id: int,
    body: VariantUpdate,
    ctx: tuple[Tenant, User] = Depends(
        require_tenant_role("owner", "admin", "manager")
    ),
    db: DatabaseSession = Depends(get_db),
):
    tenant, user = ctx
    return add_or_update_variant(db, tenant, user.id, product_id, variant_id, body)


@router.get("/export.csv")
def export_catalog_csv(
    ctx: tuple[Tenant, User] = Depends(
        require_tenant_role("owner", "admin", "manager", "analyst")
    ),
    db: DatabaseSession = Depends(get_db),
):
    """Export tenant catalog as CSV with formula-injection escaping."""
    tenant, _ = ctx
    csv_content = export_tenant_catalog_csv(db, tenant)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="catalog.csv"'},
    )


@router.post("/import")
@router.post("/import.csv", include_in_schema=False)
def import_catalog_csv(
    body: CSVImportRequest,
    ctx: tuple[Tenant, User] = Depends(
        require_tenant_role("owner", "admin", "manager")
    ),
    db: DatabaseSession = Depends(get_db),
):
    """Import products and variants from CSV text for the tenant."""
    tenant, user = ctx
    return import_tenant_catalog_csv(db, tenant, user.id, body.csv_text)

