# Requested feature map

Implemented means source and a functioning local pipeline are present. Public hosting and native PostgreSQL concurrency are separately noted below; experimental neural/price features do not imply measured superiority or causality.

| ID | Implementation location and behaviour |
| --- | --- |
| A1 | `app/models.py`, `app/catalog.py`: products and per-size SKU price/stock constraints, full note/context schema. |
| A2 | `app/main.py`, `app/security.py`: database-backed session, quiz, wishlist, cart and consented events; server-generated commerce events. |
| A3 | `app/seed.py`, `ml/calendar.py`: 2,000 users, 104 weeks, tastes/budget/loyalty/noise, trend and CNY/Hari Raya/Deepavali/promo/Mother’s Day/year-end multipliers. |
| A4 | `ml/data.py`, `ml/train.py`: null/duplicate/price/stock/quantity/key/launch checks gate training; price warnings and fingerprint. |
| B1 | `ml/recommender.py`: cutoff-fitted TF-IDF and cached cosine matrix; product similar scents. |
| B2 | Same module: item-item cosine from weighted orders, wishes and activity; also-bought endpoint. |
| B3 | Apriori max-three-item sets, support/confidence/lift rules; cart placement and explanations. |
| B4 | Eight accord weights map quiz answers; cosine match %; explicit quiz works without tracking consent. |
| B5 | Five hybrid weight candidates chosen on validation NDCG; new items use content only. |
| B6 | Shared-note and wishlisted/explored-source explanations; rule metrics shown on demand. |
| B7 | Budget, size, gender label, season, stock eligibility; browse also offers family/house. |
| B8 | Greedy MMR with .72 relevance and repeated-brand penalty. |
| B9 | Nearest eligible in-stock items for sold-out products. |
| B10 | Home uses current wishlist/cart/quiz/recent behaviour when consented; community fallback. |
| C1 | `ml/forecast.py`, admin forecasts: 108 SKU series and brand/family/all aggregation, 4–12 weeks. |
| C2 | Seasonal naive, damped ETS, calendar SARIMA and lag/rolling/calendar pooled LightGBM. |
| C3 | Three expanding validation origins; separate eight-week holdout; WAPE/sMAPE/per-SKU MASE. |
| C4 | Validation-residual 80/95% bands, measured coverage, conservative aggregate bounds. |
| C5 | Explicit Singapore holiday, promotion, Mother’s Day, year-end and time regressors. |
| C6 | Croston SBA for intermittent/low-mean SKUs; no automated high-confidence claim. |
| C7 | Revenue at current catalogue prices; recent four-vs-four-week trend. |
| C8 | Lead-time demand, normal safety-stock heuristic, reorder/stockout/overstock flags and target qty. |
| C9 | Holdout tracking and versioned future ForecastSnapshot records; worker reconciles completed weeks. |
| D1 | `analytics.py`, `Admin.jsx`: revenue/orders/AOV/observed-view conversion/repeat rate. |
| D2 | Recharts sales history, forecast and 80/95% shaded bands, units/revenue toggle. |
| D3 | Top product revenue/units, house revenue and size mix. |
| D4 | Inventory risk table, suggested qty and SKU drill-through. |
| D5 | log-RFM/standardization/K-Means; human-interpreted loyal/gift/deal aggregate labels. |
| D6 | Minted recommendation references, deduped views, CTR/cart rates; seven-day last-click revenue per slot. |
| D7 | Date-filtered overview/sales export, inventory/products/tracking CSV. |
| E1 | Temporal Precision/Recall/NDCG@5, coverage, cosine diversity; popularity baseline. |
| E2 | Seeded random allocation, assumed conversion outcomes, two-sided z-test and difference interval. |
| E3 | README table and actual versioned evaluation JSON. |
| F1 | Similar/user/quiz, SKU/summary forecast and events plus commerce/admin endpoints. |
| F2 | Precomputed content/CF, bounded LRU for static queries, live eligibility; local benchmark evidence, under-200ms deployment target. |
| F3 | Compose: native PostgreSQL, initializer, FastAPI, worker and React/nginx; persistent volumes. |
| F4 | Sunday local scheduler or opt-in GitHub training workflow, MLflow evidence, committed immutable versions, checksum and atomic manifest. |
| F5 | Per-process latency/error percentiles, held-out forecast error, recent-view/purchase PSI heuristic and alert threshold. |
| F6 | pytest API/ML suite, native concurrent-checkout test, Playwright desktop/mobile/admin journeys, GitHub Actions. |
| F7 | Root Vercel Services routes React and Python together; cloud build initialization and Neon/Supabase PostgreSQL guide. **Configured; not publicly deployed. Database provisioning is blocked by browser authentication.** |
| G1 | Default-off consent, withdrawal/personal export, no email/password in features, 180-day worker retention. |
| G2 | Per-method cards with data, purpose, metrics, controls and limitations. |
| G3 | API-guarded pin/hide and stock overrides, AuditLog records. |
| G4 | Governance risk table; discovery human-over-loop and inventory human-in-loop, research-only pricing. |
| Stretch search | Learned TF-IDF/SVD embeddings and budget/size parsing; not an LLM. |
| Stretch two-tower | Two separate learned tanh towers, negative sampling and optional serving. Training loss only. |
| Stretch elasticity | Weekly log-price/time regression per size-SKU; observational/promo-confounded. |
| Stretch session | Item2vec-style skip-gram context embeddings and optional recent-activity aggregation. |

Optional UCI Online Retail II validation has not been performed. The delivered results use simulated orders only. Payment integration is intentionally outside the requested ML portfolio scope; demo checkout never charges.
