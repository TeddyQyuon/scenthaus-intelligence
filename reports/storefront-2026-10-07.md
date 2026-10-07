# SCENTHAUS storefront update — 2026-10-07

**Completed release update:** The authorized combined storefront source `588f9d88` was deployed and verified publicly; follow-up CI `37587286866` passed 84 Python, seven frontend and ten browser tests. The later Stripe release preserves those changes and passed 119 Python, 15 frontend and 12 browser tests, including mobile and desktop checkout. Public storefront, ml/quantity Quick add and portfolio were verified. Preparation/pending/approval notes below are historical; current evidence is in [stripe-verification.md](stripe-verification.md).
Prepared locally; not pushed or deployed. Production remains on the preceding release.

## Why the opening screen lasted

`ShopProvider` previously replaced the whole application with “Opening your scent collection…” until `/auth/session` returned. The homepage then coupled catalogue fetching to optional recommendations using `Promise.all`, so a slow or failed recommendation withheld product cards. Backend cold starts and network delays can lengthen these waits; this review did not measure a cold-start duration on the user's phone.

Public home, catalogue and product pages now render without the session gate. Personal bag/account/quiz/privacy/admin routes still wait for authenticated session initialization. Mutations wait for CSRF initialization and an existing bag refresh. Initial products and optional recommendations load independently; reserved loading cards and reconnect/reload actions explain any remaining service delay.

## Shopping changes

- Quick add opens a native modal dialog or mobile bottom sheet with the product photograph, available millilitre sizes and each simulated SGD price.
- Sold-out sizes cannot be selected. The chosen variant is submitted, a synchronous guard prevents repeat submissions, and confirmation names its size and price with View bag and Keep exploring actions.
- Existing bag quantity is read after initialization; a failed add stays retryable.
- Native dialog semantics provide browser focus trapping and Escape behavior; opener focus is restored. Actual browser keyboard behavior remains to be verified after publication.
- Mobile header uses smaller branding, 44px action targets, and an explicit collection-search link. Product cards use consistent image proportions, two-line note summaries and visible size ranges.
- The identical homepage illustration is encoded as WebP: 2,117,302 → 162,170 bytes (92.34% reduction). No measured page-load speed claim is made.

## Research grounding

Reviewed first-party published content:

- Sephora Singapore fragrance listing: https://www.sephora.sg/categories/bath-and-body/fragrances — product size counts, filters, add-to-bag actions.
- Dior Singapore Sauvage: https://www.dior.com/en_sg/beauty/products/sauvage-eau-de-parfum-C099700027.html — explicit bottle-size selection and concentration information.
- Jo Malone shopping guidance: https://www.jomalone.com/customer-service/shopping-online — quick shopping with size selection before adding to the bag.

The existing production storefront was inspected in the cloud browser. These are research-informed scoped improvements within SCENTHAUS's existing visual system, not a full accessibility certification. The demo disclosures remain; no product authenticity or commercial fulfilment claim was added.

## Validation

| Check | Result |
| --- | --- |
| Production frontend build | Passed |
| Six Vitest/jsdom regression tests | Passed |
| Existing and new browser tests discovery | Eight journeys configured; actual execution pending |
| Git whitespace/diff validation | Passed |
| Actual browser verification of updated UI | Pending; local server was unreachable from the cloud browser |
| GitHub publication | Blocked by automatic approval review; remote branch remained `cc3149b8b774aa6548368ff4b003e41d343c8b15` |
| Vercel deployment | Not attempted after publication was blocked |

The six executed regressions exercise home rendering before session completion, independent catalogue rendering after failed recommendations, session reconnection, unavailable/selected size behavior and one pending submission, existing bag quantity after waiting for a session, and failed-add recovery. jsdom does not verify actual CSS layout or native browser dialog focus trapping.

## Changed files

`frontend/src/App.jsx`, `frontend/src/context.jsx`, `frontend/src/QuickAdd.jsx`, `frontend/src/api.js`, `frontend/src/styles.css`, `frontend/public/images/hero.webp`, `frontend/e2e/storefront.spec.js`, `frontend/src/tests/storefront.test.jsx`, `frontend/vitest.config.js`, `frontend/package.json`, `frontend/package-lock.json`, `.github/workflows/ci.yml`, `README.md`, `PLAN.md`, and this report.

## Release continuation

After explicit authorization to push and deploy, publish the prepared local commits to `complete-phases-real-catalog` without force pushing. Run the configured CI, then deploy to the existing `scenthaus-intelligence` Vercel project with its existing Production environment. Verify home rendering, 150 products / 35 houses, size-specific bag addition, wishlist/account routes and mobile dialog layout. Do not change or reset databases.

## Publishing continuation
Source `4f5c294` matched the prepared frontend tree exactly. Native CI completed actual model training, Python tests, Ruff and six frontend unit tests; seven of eight browser journeys passed. The consented product-view event was missed when public rendering beat session initialization, so the combined release records the view when both product data and a consented session are ready.
Git-triggered Production build `dpl_BDWoS5qzJjAxMbdS61xqVemvSDjX` failed before seed/training because Production already had migration 0003, absent from GitHub. The live CLI deployment contains the account-security extension and atomic bag additions. Those existing deployed files, tests and dependencies were recovered from Vercel Source, with matching SHA-1 file checksums, and merged with the public-loading improvements. The database was not reset, restamped or replaced.
Quick add retains fresh availability checks, explicit size selection, quantity controls, exact total, focus restoration and native Escape dismissal. Mutations wait for the session, prevent rapid repeated submissions and increment quantities atomically on the server. Source and hosted checks for this combined release remain pending.
