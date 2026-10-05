# Phase 1 — real catalog, simulated behaviour

Users, orders, stock, prices and events are **SIMULATED**. No supplier authentication claim.

| Seed 42 | Count |
|---|---:|
| Products / requested brands | 150 / 35 |
| SKU sizes observed in source metadata | 297 |
| Pseudonymous simulated users | 2,000 |
| Noisy quiz profiles | 838 |
| Weeks (2025-03-31 to 2026-09-27) | 78 |
| Orders / lines | 13,563 / 17,508 |
| Events / wishlists | 84,663 / 4,175 |
| Availability observations | 23,166 |
| Downloaded product-specific images | 150 (24.1 MB) |

| Check | Result |
|---|---|
| `node tools/pg-run.mjs .venv/bin/python scripts/verify.py --phase 1` | Alembic 0002, idempotent seed, 6 tests, lint passed |
| `npm --prefix frontend run build` | Passed |
| Generator repeatability / stockout exclusion / consent / invalid product / invalid JWT | Passed |
| Catalog coverage / unique image hashes / source and size validation | Passed |

New dependencies: PyJWT (signed HttpOnly cookie with server-side revocation and CSRF), PyYAML. Existing quiz_profiles table plus users.quiz_profile; variants hold stock; stock_weeks stores simulated availability. Images retain source URLs and checksum metadata; three representative bottle images visually inspected. Models receive pseudonymous IDs, not email/password data. Hidden tastes are never exported. Inherited migration 0001 uses current metadata; additive migration 0002 guards columns for both fresh and existing databases. Catalog seed refuses to overwrite an existing database; use a separate empty demo database when replacing the fictional catalog. PGlite does not prove native PostgreSQL concurrent locking. Unknown concentration metadata is preserved as Unverified rather than guessed.
