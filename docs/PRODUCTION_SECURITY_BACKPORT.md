# Production security maintenance, 5 November 2026

The public storefront uses `complete-phases-real-catalog`. This release backports dependency security maintenance to that branch without introducing main's multi-tenant schema, migration 0005/0006, or tenant APIs. Existing storefront discovery and responsive images are retained. The tenant isolation and domain-ownership fixes remain on main for its separate multi-tenant release; they are not applicable to the single-store production schema.

Updated Vite/Vitest and locked transitive dependencies, cryptography, MLflow and training/reference packages. Vercel's CPU PyTorch bootstrap now installs 2.13.0 consistently with the training requirements. The CPU-only wheel is installed without dependencies first; the next complete requirements installation resolves dependencies from PyPI. TLS and package verification remain enabled.

Validation before release:

- 22 frontend unit tests, production frontend build and npm audit pass with zero advisories.
- 37 existing backend startup and signed-payment contract tests pass against disposable SQLite fixtures.
- Twelve pure ML tests pass on PyTorch 2.13.0+cpu, including forecast model gradients and recommender cold-start behavior.
- The broader ML selection had six failures caused by missing local seeded database/trained artifacts. These are not represented as passing. Full training and artifact-backed behavior must be verified by the Vercel build and hosted checks.
- The installed training environment audit reports zero advisories; its local-version CPU torch wheel is not listed by PyPI. The corresponding base torch==2.13.0 advisory check separately passes with zero advisories.
- Ruff passes for the changed build module; git diff --check passes.

Deployment and live validation will be recorded after the build completes. No production data was reset and no live payment was submitted by local validation.
