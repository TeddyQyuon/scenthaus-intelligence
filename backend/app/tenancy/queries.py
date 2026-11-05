"""Explicit tenant predicates for the legacy storefront and reporting services.

These queries protect application data even when the database role bypasses RLS.
They deliberately do not install global ORM hooks: merchant accounts may have
memberships in stores other than the store where their login account was created.
"""

from sqlalchemy import delete, inspect, select, update
from sqlalchemy.orm import with_loader_criteria

from .constants import DEFAULT_TENANT_ID


def active_tenant_id(db):
    return db.info.get("tenant_id", DEFAULT_TENANT_ID)


def tenant_select(db, *entities):
    from ..database import Base

    statement = select(*entities)
    models = {
        item["entity"]
        for item in statement.column_descriptions
        if item.get("entity") is not None
    }
    for model in models:
        if hasattr(model, "tenant_id"):
            statement = statement.where(model.tenant_id == active_tenant_id(db))
    # Join targets may be added after constructing the SELECT. Loader criteria
    # keep those tables scoped too, including old cross-tenant cart/wishlist rows.
    for mapper in Base.registry.mappers:
        model = mapper.class_
        if hasattr(model, "tenant_id"):
            statement = statement.options(
                with_loader_criteria(
                    model,
                    model.tenant_id == active_tenant_id(db),
                    include_aliases=True,
                )
            )
    return statement


def tenant_get(db, model, identifier):
    if not hasattr(model, "tenant_id"):
        return db.get(model, identifier)
    # A fresh tenant-qualified SELECT is required even if the identity map already
    # contains this primary key from an earlier authorization/lookup operation.
    primary_key = inspect(model).primary_key
    if len(primary_key) != 1:
        raise ValueError("Tenant lookup requires a single primary key")
    return db.scalar(tenant_select(db, model).where(primary_key[0] == identifier))


def tenant_update(db, model):
    statement = update(model)
    return (
        statement.where(model.tenant_id == active_tenant_id(db))
        if hasattr(model, "tenant_id")
        else statement
    )


def tenant_delete(db, model):
    statement = delete(model)
    return (
        statement.where(model.tenant_id == active_tenant_id(db))
        if hasattr(model, "tenant_id")
        else statement
    )
