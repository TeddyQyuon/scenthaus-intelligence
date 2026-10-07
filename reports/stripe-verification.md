# Stripe checkout verification — 2026-10-07

This report distinguishes implementation tests from actual hosted payment verification. Stripe is configured in **test mode**, with no real charge or dispatch.

## Local implementation checks

- 35 checkout backend contract/security tests passed. They use the real Stripe signature verifier and isolated SQLite locally; native CI uses isolated PostgreSQL schemas and actual concurrency.
- 15 frontend unit tests passed: seven storefront regressions and eight checkout regressions.
- Production Vite build passed; Ruff passed; diff whitespace checks passed.
- Covered authoritative integer prices, forbidden client totals/discounts, identity and quantity validation, stale price/stock, stable idempotency/retries, ownership/CSRF, direct success reads, signed payment confirmation, signature/timestamp/mode/amount rejection, async payment success/failure, declined-card retries, cancellation/expiry, partial/full refunds and stock reconciliation.
- Mobile and desktop browser checkout regression journeys added to the native CI suite; these fail closed when CI payment credentials are absent.

- The actual Stripe test API accepted the server SDK parameters, SGD currency and 12,990-cent validation amount; that session was expired without payment. This validates API compatibility, not completed-payment fulfilment.

## Deployment and real Stripe verification

Release deployment, full native CI and hosted Checkout test outcomes will be recorded here after validation. Do not treat mocked gateway tests as evidence of a successful hosted Stripe payment. Environment keys are stored outside Git and are excluded from this report.

## Merchant limits

Seeded prices/inventory remain portfolio data. Delivery policy is Singapore only, complimentary shipping, no discounts and no additional tax. No fulfilment or SCENTHAUS email delivery service is provided. Live keys and a separate live webhook, merchant inventory/tax/shipping/legal review and fulfilment readiness are required before accepting real customer money.
