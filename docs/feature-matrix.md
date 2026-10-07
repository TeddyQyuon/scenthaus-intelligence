# Feature matrix

This matrix describes the current `complete-phases-real-catalog` source. Products are real references; historical activity, prices and inventory are seeded portfolio data. The storefront upgrade is deployed, and the Stripe checkout release is verified separately in `reports/stripe-verification.md`.

| Area | Implemented behaviour | Source |
| --- | --- | --- |
| Catalogue | 150 fragrances across 35 brands, 297 size variants, product-specific images, product details and source links | `backend/app/real_catalog.json`, `backend/app/catalog.py`, `frontend/src/App.jsx` |
| Discovery | Product filters, natural-language query parsing, BM25/dense/hybrid retrieval, similar scents and substitutions | `backend/app/main.py`, `ml/search.py` |
| Recommendations | Hybrid baseline, cached two-tower candidate scoring, quiz cold start, cart associations, shared-note/accord reason tags | `backend/app/main.py`, `backend/app/ml/recommender.py`, `ml/rec_serving.py` |
| Checkout | Server-priced SGD quotes, Stripe-hosted payment, immutable numbered orders, signed idempotent webhooks, stock reservations, cancellation and refunds; currently Stripe test mode | `backend/app/checkout.py`, `backend/app/stripe_service.py`, `frontend/src/Checkout.jsx` |
| Consent and privacy | Default-off personalization, ephemeral no-consent quiz, event gate, export and withdrawal | `/privacy/consent`, `/privacy/export`, `/events`, `frontend/src/App.jsx` |
| Admin | Protected overview, forecast/model picker, accuracy comparison, inventory signals, model registry/health, product and stock controls, exports | `/admin/*`, `frontend/src/Admin.jsx` |
| Evaluation | Chronological recommendation/forecast evaluations and drafted search labels, with baselines and explicit synthetic-data limitations | `ml/reports/`, `docs/model_cards/` |
| Serving | Immutable versioned model bundle, integrity checks, Vercel CPU API runtime and quantized ONNX query encoder | `backend/app/ml/serving.py`, `backend/app/vercel_init.py`, `ml/embeddings.py` |
| Deployment | Vercel Services config, SPA/API routing, protected daily maintenance endpoint, catalog-release guard | `vercel.json`, `backend/app/vercel_init.py` |
| Verification | Python API/model tests, Ruff, frontend unit regressions and desktop/mobile Playwright journeys in GitHub Actions | `.github/workflows/ci.yml`, `backend/tests/`, `ml/tests/`, `frontend/e2e/` |

## Not provided

- Real-time retailer stock, verified product authenticity, live merchant fulfilment, tax/legal readiness or shipping operations.
- A human-reviewed search relevance dataset or claims of real-customer preference, forecast accuracy or commercial uplift.
- Automated purchasing, replenishment, pricing or consequential customer classification.
- Live-mode Stripe activation. Test payments take no real money or dispatch fragrance; see [checkout limits](stripe-checkout.md).
