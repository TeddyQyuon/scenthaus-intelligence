# Stripe checkout verification — 2026-10-07

SCENTHAUS is deployed with real **Stripe-hosted Checkout in test mode**. The demo payment endpoint is retired. An actual hosted sandbox payment, original Stripe webhook confirmation, declined card, cancellation, refresh and genuine-event retries were verified against the public deployment. No real charge or dispatch occurred.

## Changes and architecture

The existing React/Vite storefront and FastAPI/PostgreSQL architecture were preserved. Public home/catalogue rendering no longer waits for session/bag/recommendation initialization; the hero asset is about 92% smaller. Quick add selects ml and quantity, checks current availability and adds atomically to the saved bag. Mobile navigation, spacing, loading states and catalogue cards were refined using first-party fragrance retail benchmarks without copying their branding.

The checkout flow uses a server-priced quote, validated product/size/variant identities and quantities, integer SGD cents, one immutable numbered pending order, atomic stock reservations and a stable order-derived Stripe idempotency key. Card details go directly to Stripe. Eligible account payment methods are supported; adaptive currency conversion is disabled to preserve SGD. Signed webhook confirmation is the sole authority for paid status. Transactional event deduplication and row locking prevent repeat fulfilment effects. Owner-only order pages survive refresh; cancellation and verified expiration release reserved stock once and preserve the bag. Refund handling is monotonic and never assumes physical returns.

## Published releases

| Item | Verified result |
|---|---|
| Storefront branch | `complete-phases-real-catalog` |
| Integration commit | `20c82928ad7ee95d913b87ab4ebcaf8c07f58165` — `feat: replace demo checkout with secure Stripe payments` |
| Final runtime source | `2398d7504b3a014105aca83f22655153ca8c02a8` |
| Exact runtime Git tree | `f750976cdc8daba6e1ce39e9569172544b60a1b4` |
| Native CI | [Run 37598572781](https://github.com/TeddyQyuon/scenthaus-intelligence/actions/runs/37598572781), successful |
| Vercel runtime deployment | `dpl_9z9jBRE2CS8fiMTQxcMDXpVEr11e`, Ready and promoted to the existing public Production domain |
| Checkout | https://scenthaus-intelligence.vercel.app/checkout |
| Webhook | https://scenthaus-intelligence.vercel.app/api/stripe/webhook — registered in Stripe test mode |
| Portfolio source | `9b0001c4b908f8dd0cd2573f35d47e8cd802f6b3`, exact tree `8a1839536ce7e896e7b156ac5def7d6b933eb13e` |
| Portfolio deployment | `dpl_4Mx6bWbpoQg9FaXQkLXV8CXCfico`, Ready with public alias |
| Portfolio case study | https://teddy-qyuon-portfolio.vercel.app/projects/scenthaus-intelligence — verified Stripe content and actual checkout/payment screenshots |

The evidence publication changes documentation only; retain the verified runtime deployment instead of retraining for documentation. Existing Production/Preview databases, unrelated APIs and historical ML metrics are preserved.

## Tests and results

- **119 Python tests passed** in native CI with PostgreSQL, actual model training and isolated checkout schemas, including competing payment requests and competing distinct paid events. This includes **35 Stripe checkout contract/security tests** using the real Stripe HMAC verifier with controlled gateway responses.
- **15 frontend unit tests passed**: seven storefront regressions and eight checkout regressions.
- **12 Playwright journeys passed**, including 1440px desktop and 390px mobile checkout layouts, discovery, consent, wishlist/bag, account security and data-export journeys.
- Frontend production build, Ruff and whitespace checks passed.
- Portfolio production build passed. Four security checks passed; one Windows-only alternate-data-stream check was skipped on Linux. The existing approximately 535 kB portfolio JS chunk warning remains advisory.
- Official Stripe SDK request compatibility was additionally verified with actual test sessions; those validation-only sessions were expired without payment.

| Requested scenario | Evidence and result |
|---|---|
| Successful payment | Actual hosted test card payment on public site: Dior Sauvage 100 ml, quantity 1, **S$193.01 / 19,301 cents SGD**. Original signed Stripe webhook confirmed `SCENT-2026-000002`; browser returned to the success page with confirmed status and bag cleared. |
| Declined payment | Actual hosted declined test card produced Stripe's useful decline message for **S$138.48**. Order `SCENT-2026-000003` never became paid. |
| Checkout cancellation | Actual Stripe session expiration through owner cancellation; page states no completed payment and keeps the selected bag. A separate staged cancellation was also verified. |
| Double-click Pay now | Frontend synchronous submission guard and backend/PostgreSQL concurrent request tests passed; only one gateway session/order is created. |
| Refresh success page | Actual deployed success refresh preserved order `SCENT-2026-000002` and confirmed status; unit/API tests establish that reads cannot create orders. |
| Manipulated prices | Backend tests reject client total/discount/price fields and stale quotes; official database variant prices determine the charge. |
| Invalid product ID | Backend strict validation and authority checks passed. |
| Invalid quantity | Strict integer limits reject zero, negative, fractional, boolean and excessive quantities; tests passed. |
| Webhook retry | The actual genuine Stripe `checkout.session.completed` event was retrieved after original confirmation and replayed with valid signatures **three times**, each HTTP **200**. Same order persisted; native PostgreSQL tests verify one stock/cart/purchase effect, including distinct concurrent event IDs. |
| Direct success navigation without paying | Backend and frontend tests plus mobile/desktop browser journeys never display a paid confirmation without an owned paid order. |
| Mobile checkout | Native Playwright 390px layout, fields, totals, button, retained bag and no horizontal overflow passed. |
| Desktop checkout | Native Playwright 1440px two-column layout and same authority/empty/error checks passed. |

Independent actual Stripe API reads found **exactly one session** for each tested order: the successful session is complete/paid in SGD, and the declined session is expired/unpaid. Refreshing the cancelled page preserved the same unpaid order and bag.

## Security verification

- Secret/public environment boundaries reviewed. Actual Stripe secret and webhook signing secret were scanned against 324 tracked/candidate files, frontend build artifacts and all available Git patch history: **no matches**. Actual keys never enter source, examples, reports, frontend APIs or screenshots.
- Raw-body signature and timestamp verification, mode/session/order/amount/currency matching, invalid signatures, refunds and async outcomes passed tests.
- Official integer prices and strict schemas block client amount/discount/quantity manipulation; database cart authority avoids trusting localStorage.
- Owner checks, same-origin/CSRF mutation checks, rate limits, safe public errors, ORM parameterization, React escaping and HTTPS Stripe redirect validation reviewed/tested.
- Concurrency fixes refresh locked ORM state after waiting, preventing stale status from applying the purchase twice. Stable retries preserve uncertain reservations until Stripe establishes the outcome.
- No raw card data is collected by SCENTHAUS or saved in its database. Browser test cards were fictitious; saving payment information was disabled.
- Browser app console showed no app errors after the deployed checks. Vercel error-log query for the final deployment covering the actual payment tests returned no runtime errors. Expected Stripe decline messages were displayed in its hosted UI.

## Environment configuration

These are already configured for the storefront's Vercel Production environment; examples contain placeholders only. Hosted Checkout does not need a frontend Stripe SDK.

| Variable | Purpose |
|---|---|
| `VITE_STRIPE_PUBLISHABLE_KEY` | Matching public test key; reserved for future embedded Stripe UI |
| `STRIPE_SECRET_KEY` | Sensitive backend-only Stripe test API key |
| `STRIPE_WEBHOOK_SECRET` | Sensitive backend-only signing secret for the registered test endpoint |
| `CHECKOUT_PUBLIC_URL` | `https://scenthaus-intelligence.vercel.app` — server-owned return origin |

Webhook events: `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `checkout.session.async_payment_failed`, `checkout.session.expired`, `payment_intent.payment_failed`, `charge.refunded`. Test/live endpoint secrets must match their account and mode. Existing database/auth/CSRF/cron variables retain their current roles. See [configuration and operations](../docs/stripe-checkout.md).

## Files created

- `backend/alembic/versions/0004_stripe_checkout.py`
- `backend/app/checkout.py`
- `backend/app/stripe_service.py`
- `backend/tests/test_stripe_checkout.py`
- `docs/stripe-checkout.md`
- `frontend/e2e/checkout.spec.js`
- `frontend/src/Checkout.jsx`
- `frontend/src/tests/checkout.test.jsx`
- `reports/stripe-verification.md`

## Files modified

- `.env.example`
- `.gitignore`
- `PLAN.md`
- `README.md`
- `backend/.env.example`
- `backend/app/analytics.py`
- `backend/app/config.py`
- `backend/app/main.py`
- `backend/app/maintenance.py`
- `backend/app/models.py`
- `backend/pyproject.toml`
- `backend/requirements.txt`
- `backend/tests/test_api.py`
- `backend/tests/test_postgres_concurrency.py`
- `docs/architecture.md`
- `docs/deployment.md`
- `docs/feature-matrix.md`
- `docs/portfolio-entry.md`
- `frontend/e2e/journeys.spec.js`
- `frontend/src/App.jsx`
- `frontend/src/QuickAdd.jsx`
- `frontend/src/styles.css`

Evidence-only final updates also modify `reports/deployment.md` and `reports/storefront-2026-10-07.md`. Portfolio files: modified `src/data/projects.js`; created `src/assets/images/projects/scenthaus/checkout-verified.jpg` and `src/assets/images/projects/scenthaus/payment-confirmed.jpg`.

## Remaining merchant limitations

The integration is end-to-end verified **in Stripe test mode**. Live charging is not enabled because only test credentials were provided. Seeded prices/stock and supplier authenticity require merchant review. Current policy is Singapore only, complimentary shipping, zero discounts and zero additional tax; GST/tax, shipping/refund/legal policies must be finalized before accepting real money. Configure live credentials and a separate live webhook, then repeat merchant acceptance tests.

There is no SCENTHAUS transactional email or fulfilment service; the page does not falsely claim email delivery. Stripe receipt sending depends on account settings. Guest order access depends on retaining the owning browser session; registered accounts provide durable access. Reservation reconciliation runs on checkout review and in existing daily maintenance (three oldest per run); larger merchant volumes need dedicated scheduling and operational monitoring.
