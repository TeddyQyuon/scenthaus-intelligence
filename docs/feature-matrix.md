# Feature matrix

This matrix describes the current `complete-phases-real-catalog` source. It does not describe the older storefront still attached to the public Vercel alias. Products are real references; users, orders, prices and inventory are simulated.

| Area | Implemented behaviour | Source |
| --- | --- | --- |
| Catalogue | 150 fragrances across 35 brands, 297 size variants, product-specific images, product details and source links | `backend/app/real_catalog.json`, `backend/app/catalog.py`, `frontend/src/App.jsx` |
| Discovery | Product filters, natural-language query parsing, BM25/dense/hybrid retrieval, similar scents and substitutions | `backend/app/main.py`, `ml/search.py` |
| Recommendations | Hybrid baseline, cached two-tower candidate scoring, quiz cold start, cart associations, shared-note/accord reason tags | `backend/app/main.py`, `backend/app/ml/recommender.py`, `ml/rec_serving.py` |
| Demo commerce | Session-backed account, wishlist, cart, demo checkout and order history; no payment or fulfilment | `backend/app/main.py`, `frontend/src/App.jsx` |
| Consent and privacy | Default-off personalization, ephemeral no-consent quiz, event gate, export and withdrawal | `/privacy/consent`, `/privacy/export`, `/events`, `frontend/src/App.jsx` |
| Admin | Protected overview, forecast/model picker, accuracy comparison, inventory signals, model registry/health, product and stock controls, exports | `/admin/*`, `frontend/src/Admin.jsx` |
| Evaluation | Time-based recommendation/search/forecast reports with baselines and explicit synthetic-data limitations | `ml/reports/`, `docs/model_cards/` |
| Serving | Immutable versioned model bundle, integrity checks, Vercel CPU API runtime and quantized ONNX query encoder | `backend/app/ml/serving.py`, `backend/app/vercel_init.py`, `ml/embeddings.py` |
| Deployment | Vercel Services config, SPA/API routing, protected daily maintenance endpoint, catalog-release guard | `vercel.json`, `backend/app/vercel_init.py` |
| Verification | Python API/model tests, Ruff, and three Playwright journeys in GitHub Actions | `.github/workflows/ci.yml`, `backend/tests/`, `ml/tests/`, `frontend/e2e/` |

## Not provided

- Real-time retailer stock, verified product authenticity, payment processing, shipping or fulfilment.
- A human-reviewed search relevance dataset or claims of real-customer preference, forecast accuracy or commercial uplift.
- Automated purchasing, replenishment, pricing or consequential customer classification.
- A current production deployment of this source. The public alias still serves a previous release; see [`reports/deployment.md`](../reports/deployment.md).
