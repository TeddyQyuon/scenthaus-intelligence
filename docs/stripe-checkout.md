# Stripe checkout configuration and operations

SCENTHAUS uses **Stripe-hosted Checkout**, created by the existing FastAPI service. The storefront keeps its catalogue, Quick Add, bag, recommendation features, routes, account security and React/Vite branding. Card numbers are entered on Stripe, never sent through SCENTHAUS.

## Payment architecture

1. `/api/checkout/quote` loads the signed-in or guest customer's database bag, validates current products, sizes, quantities and stock, and returns an HMAC quote of authoritative SGD amounts in integer cents.
2. `/api/checkout/session` accepts only contact/delivery information, product/variant/size identities, quantities, quote token and an idempotency key. It recalculates prices, rejects stale or manipulated inputs, locks the customer, creates one numbered pending order and atomically reserves stock.
3. The backend creates the Checkout Session with a stable order-derived Stripe idempotency key. Repeated requests and tabs reuse the existing checkout. Network uncertainty keeps the reservation until Stripe establishes its outcome.
4. `/api/stripe/webhook` verifies Stripe's signature over the untouched request body with a 300-second tolerance. Matching session, mode, amount, currency and order reference are mandatory. Only signed `checkout.session.completed` with paid status or `checkout.session.async_payment_succeeded` can confirm payment. Merely reading the success page or retrieving a paid session never confirms an order.
5. A transaction records the minimal event identifier, confirms the existing order once, and removes only purchased bag quantities. Retries cannot consume stock or create purchase records twice. Async failure/verified expiry release stock once. Card declines stay retryable. Partial/full refund events are monotonic; refunds do not imply physical stock returns.

Pending/failed checkouts are excluded from sales/recommendation purchase queries; historical simulated orders remain. Snapshots preserve purchased names, brands, bottle sizes, prices and delivery details. Public order details are available only to the owning account/guest session. Guest customers should retain their browser session; registering before purchase gives durable account access.

## Environment variables

Configure these for the Vercel **Production** environment before deploying; use a separate Stripe test account/configuration for branch previews. Never put server credentials into Vite variables or source files.

| Variable | Where | Value |
|---|---|---|
| `STRIPE_SECRET_KEY` | API/server, sensitive | Stripe test secret; switch to a live secret only after merchant launch review |
| `STRIPE_WEBHOOK_SECRET` | API/server, sensitive | Signing secret of the endpoint registered for the same Stripe mode/account |
| `CHECKOUT_PUBLIC_URL` | API/server | `https://scenthaus-intelligence.vercel.app` |
| `VITE_STRIPE_PUBLISHABLE_KEY` | Frontend/public | Matching test publishable key; reserved for a future embedded payment UI |

Hosted Checkout redirects to the server-issued Stripe URL and does not require Stripe.js or a publishable key to run. The publishable placeholder is provided as requested; no extra frontend payment SDK is necessary. Existing `DATABASE_URL`, `SECRET_KEY`, `ALLOWED_ORIGINS`, `CRON_SECRET` and other deployment variables retain their current responsibilities. Secrets are excluded by the ignore rules. Examples contain placeholders only.

## Webhook registration

Production-domain endpoint (currently Stripe **test mode**):

`https://scenthaus-intelligence.vercel.app/api/stripe/webhook`

Enable these events:

- `checkout.session.completed`
- `checkout.session.async_payment_succeeded`
- `checkout.session.async_payment_failed`
- `checkout.session.expired`
- `payment_intent.payment_failed`
- `charge.refunded`

Use the signing secret belonging to that exact endpoint, not the API secret or a local CLI forwarding secret. No browser login/CSRF header is required for Stripe's webhook; its signature is mandatory. Other state-changing checkout routes retain same-origin and CSRF validation. Test and live webhook secrets are distinct. Stripe retries failed webhook deliveries; monitor and resend failed events from Stripe Workbench.

## Local test mode

Set server test environment variables outside Git and use `CHECKOUT_PUBLIC_URL=http://localhost:5173`. Run migrations with `alembic upgrade head`, start the existing API and Vite app, then use the official Stripe CLI:

```sh
stripe listen --events checkout.session.completed,checkout.session.async_payment_succeeded,checkout.session.async_payment_failed,checkout.session.expired,payment_intent.payment_failed,charge.refunded --forward-to localhost:8000/stripe/webhook
```

Set the resulting local signing secret in the API environment and restart. Use Stripe's official test cards on hosted Checkout: `4242 4242 4242 4242` succeeds, `4000 0000 0000 0002` declines, with a future expiry and test CVC. Never use real cards in test mode. Do not create fake signed "paid" events against live orders.

## Delivery, receipts and launch limitations

The initial explicit policy is **Singapore delivery only, complimentary standard shipping, no discounts, no additional tax**. Product amounts remain the existing seeded catalogue prices. Confirm supplier authenticity, real inventory, shipping, GST/tax treatment, refunds, legal policies and fulfilment before enabling live payments. Those merchant facts cannot be inferred from the portfolio dataset. Test payments reserve the existing test inventory and never promise dispatch.

Stripe receives the receipt email; actual receipt sending depends on the account's email settings. SCENTHAUS does not claim a separate confirmation email was sent and does not implement a fulfilment/email service in this change. Dashboard-eligible payment methods are supported without hardcoding a card-only list; async outcomes wait for signed confirmation.

Expired reservations are reconciled on checkout review and in the existing daily authenticated maintenance job. Stripe's verified expired/unpaid state is required to release a known session. A lost creation response is recovered through a bounded Stripe listing; an incomplete listing or unavailable Stripe API keeps the reservation for operator review instead of guessing. Daily maintenance processes three oldest reservations per run; monitor larger volumes and schedule a dedicated worker if scaling beyond this project's traffic. Missing webhook confirmation remains pending; resending the genuine Stripe event is the recovery path.

## Verification

Local checkout contract/security tests use Stripe's actual signature verifier and mocked network calls. Native CI repeats these against isolated PostgreSQL schemas, including concurrent requests. Frontend tests cover double submissions, server totals, failure feedback, cancelled checkout, direct success navigation and refresh. Browser journeys check desktop/mobile layout while CI has no payment credentials and must fail closed. Actual hosted test payment/webhook verification must additionally be performed on the deployed release; see `reports/stripe-verification.md` for recorded results.
