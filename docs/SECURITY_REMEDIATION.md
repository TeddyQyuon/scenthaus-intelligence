# Tenant isolation and custom domain remediation

Legacy storefront, checkout, customer events, analytics and admin queries now apply tenant predicates in application SQL. Scoped primary-key lookups issue a qualified SELECT even if another tenant's object is cached in the session. Joined tenant tables are scoped too. Writes stamp the active tenant; merchant routes check store membership or an admin account belonging to that store. Customer sessions must belong to the selected storefront; a store owner can retain their platform account while managing a membership in another store.

Offline recommendation, search, forecast and evaluation artifacts currently belong to the default demo store. Other stores receive HTTP 503 for these features until tenant-specific artifact storage is available. Their catalog, cart, checkout, customer and merchant functionality remains available. Tenant-selected catalogs and configuration responses are not shared-cacheable.

## Deployment

1. Install the synchronized backend requirements and frontend lockfile.
2. Run `alembic upgrade head` from `backend/` before activating the new backend. Revision `0006` creates the expiring domain ownership challenge table defensively; the migration can run again safely.
3. Deploy the backend and frontend together. Purge any previously cached catalog/configuration responses if the hosting platform does not invalidate them automatically on deployment.
4. Existing domain mappings with no `verified_at` remain inactive. A merchant must register a claim with `POST /tenant/domains`, publish its returned TXT proof, then call `POST /tenant/domains/{claim_id}/verify`. Claims expire after 24 hours; DNS lookups have bounded timeouts. Claims may coexist across stores, so pending claims cannot reserve someone else's domain. Only successful current DNS proof activates or reclaims a mapping.

The migration and these checks were executed only against disposable local SQLite databases. No production database, deployment setting or DNS record was changed. PostgreSQL production role/RLS behavior and PostgreSQL concurrency tests still require the normal PostgreSQL CI/staging environment.

## Verification

On the pinned serving dependencies, 60 targeted tests pass: 23 isolated tenant/domain/analytics regression cases, 2 startup/catalog cases and 35 existing Stripe checkout cases. Twelve existing sequential account-security tests also pass against a disposable SQLite database; three PostgreSQL-specific migration/concurrency tests were excluded. Ruff and `git diff --check` pass. DNS is mocked; tests cover pending/reclaimed domains, cross-tenant claim access, wrong proof, consumed proof, expiry, expiry during lookup, timeout and repeatable migration.
