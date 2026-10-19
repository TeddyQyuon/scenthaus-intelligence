"""Multi-tenant real-data intelligence: live search, tiered cold-start recommendations, and gated inventory signals."""

from .tiered_engine import (
    recommend_tenant_products,
    router,
    search_tenant_products,
    tenant_inventory_intelligence,
)

__all__ = [
    "recommend_tenant_products",
    "router",
    "search_tenant_products",
    "tenant_inventory_intelligence",
]
