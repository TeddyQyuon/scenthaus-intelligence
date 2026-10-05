# PLAN.md
Tick [x] when a phase's Done-when checks pass.

## Assumptions
- Latest user instructions override Docker and phase pauses: use Vercel and finish all phases in order.
- Workspace maintenance removed unpushed phase work on 2026-10-05. Recovered published GitHub main 22c3c35; all phase checks below are rerun on the recovered app.
- Reuse the existing React/Vite JavaScript storefront and Python service. No Next.js or legacy directory is present.
- The catalog contains real products across the user's 35 brands. Source links identify manufacturer versus retailer images. Prices, stock, orders, users, events, catalog availability dates and wear annotations are simulated; supplier authenticity and real checkout are not verified.
- Native PostgreSQL/Docker are unavailable here. Local SQL checks use PGlite's PostgreSQL wire protocol; CI also runs native Postgres. PGlite cannot prove production TLS or concurrent row-lock behavior.
- All hyperparameters are YAML, seed 42 unless a phase requires three seeds. Only time-based splits; no simulated data or trained weights committed.
- Preserved original phase requirements below; all Docker checks mean equivalent native/Vercel process checks under the user's explicit override.

- Phase 3 warm latency is measured with TestClient + PGlite; it is not a network or Vercel guarantee. Collaborative filtering remains stronger than the trained two-tower model on the shared simulated test split.

## Phases

[x] PHASE 0: SCAFFOLD
Goal: a monorepo that runs end to end with empty features.
- frontend/: React + Vite + React Router
- backend/: FastAPI, SQLAlchemy, Alembic, GET /health
- ml/ (package, configs/, reports/) and data/
- docker-compose.yml: frontend, api, postgres
- ruff config, pytest in backend and ml, .gitignore, git init
- Fill in the Commands section of AGENTS.md
Done when: docker compose up serves the frontend and /health,
and tests + lint pass.

[x] PHASE 1: DATA
Goal: realistic simulated data in Postgres + event logging.
- Tables: products, users (with quiz_profile), events, orders,
  order_items, stock
- Seed ~150 fragrances (reuse /legacy products if present,
  else invented brands): concentration, top/heart/base notes,
  accords, season, occasion, longevity, sillage, price per
  size, stock
- ml/data/generate_orders.py: ~2,000 users with hidden taste
  profiles (quiz profiles for ~40%, noisy), 18 months of
  orders with trend, seasonality, promo weeks, occasional
  stockouts and SG spikes (CNY, Hari Raya, Deepavali,
  9.9/11.11/12.12, Mother's Day, year-end)
- Guest session IDs + JWT login with an admin role
- POST /events: view, wishlist, cart, purchase, quiz_submit
- Validation checks: nulls, duplicates, price outliers
Done when: one command seeds the DB reproducibly (fixed seed),
validation passes, and tests cover the generator and /events.

[x] PHASE 2: BASELINES + EVAL HARNESS
Goal: baselines every DL model must beat, one shared harness.
- Time-based train/val/test split with a leakage test
- Metrics: Recall@K, NDCG@K, MRR, coverage, diversity (recs);
  WAPE, sMAPE, MASE, interval coverage (forecasts)
- Recommender: popularity + item-item collaborative filtering
- Search: BM25 over product text
- Forecast: seasonal naive + global LightGBM (lags, calendar,
  SG holidays)
- One command writes ml/reports/baselines.md
Done when: baselines.md reproduces from a fresh seed, and
tests cover the split and every metric.

[x] PHASE 3: TWO-TOWER RECOMMENDER
Goal: a PyTorch two-tower model, evaluated honestly vs Phase 2.
- Training pairs from purchase/cart/wishlist/view, weighted
  purchase > cart > wishlist > view
- Negative sampling: random, popular, hard
- User tower: ID embedding + recent items + quiz features
- Item tower: ID embedding + notes/accords + text embedding
  (sentence-transformers all-MiniLM-L6-v2) + price band
- In-batch softmax loss with temperature (BPR as ablation)
- Early stopping, LR schedule, seeds, checkpoints, YAML config
- Cold start: quiz-only users, content-only new items
- Precomputed item embeddings, top-K with NumPy
- Reason tags per result (shared notes/accords)
- Ablations: no content, no history, no quiz
- API: /recommend/user, /recommend/similar, /recommend/quiz
Done when: ml/reports/recommender.md compares two-tower,
ablations and baselines (even if baselines win), endpoints
answer in <100 ms from cached embeddings, and tests pass.

[ ] PHASE 4: SEMANTIC SEARCH
Goal: natural-language search, compared honestly with BM25.
- Product text builder: name, brand, notes, description
- sentence-transformers embeddings (all-MiniLM-L6-v2), cached
- Query parser: price, size, gender label and season become
  SQL filters; the remaining text is embedded
- Dense retrieval + hybrid (BM25 + dense, reciprocal rank
  fusion)
- Draft 60 labeled queries in ml/data/search_eval.json and
  flag them for my manual review
- Compare BM25 / dense / hybrid on MRR and NDCG@10
- GET /search?q= with a query-embedding cache
Done when: ml/reports/search.md has the comparison, /search
handles "fresh office scent under $150", and tests pass.

[ ] PHASE 5: DL FORECASTING
Goal: LSTM and N-BEATS forecasters, compared fairly vs Phase 2.
- Weekly units per SKU and category; lookback and horizon
  in YAML
- Features: lags, calendar, SG holidays, promos, price;
  per-series scaling; flag stockout weeks
- Global LSTM with SKU embeddings (multi-horizon)
- N-BEATS
- Quantile (pinball) loss for P10/P50/P90
- Rolling-origin backtests: WAPE, sMAPE, MASE, interval
  coverage
- 3 seeds per model, report mean and variance
- API: GET /forecast/sku/{id}, GET /forecast/summary
Done when: ml/reports/forecast.md compares seasonal naive,
LightGBM, LSTM and N-BEATS (even if LightGBM wins), and
tests pass.

[ ] PHASE 6: TRACKING + SERVING
Goal: reproducible runs and a one-command stack.
- MLflow tracking in every training script: params, metrics,
  artifacts, dataset version hash
- Versioned model folders with a current.json pointer and a
  rollback script
- API loads the current models at startup and returns the
  model version in responses
- Add mlflow to docker-compose; a Dockerfile for ml jobs
Done when: docker compose up runs the whole stack and a
training run appears in MLflow.

[ ] PHASE 7: REACT UI
Goal: storefront and admin pages that use the ML endpoints.
- If /legacy (old Next.js app) exists, port its components,
  CartContext, quiz and wishlist to React Router; otherwise
  build a minimal storefront
- "Picked for you" row with reason chips (/recommend/user)
- Quiz results page (/recommend/quiz)
- Search bar with example-query chips (/search)
- /admin/forecast (JWT protected): model picker, P10-P90 band
  chart with Recharts, accuracy table
- "About this model" modal: version, date, "simulated data"
- Send view, wishlist, cart and purchase events to /events
Done when: npm run build passes, the flows work against the
API, and one smoke test passes.

[ ] PHASE 8: DOCS + RESPONSIBLE AI
Goal: a portfolio-ready repo.
- README: Mermaid architecture diagram, 3-command setup,
  results tables from ml/reports/, ablation findings,
  limitations (simulated data, small catalog)
- Model cards in docs/model_cards/ (recommender, search,
  forecaster): purpose, data, metrics, limits
- Personalization consent toggle (PDPA-aware); only
  pseudonymous IDs in model features
- docs/portfolio-entry.md: title, 3-line summary, key metrics
  from ml/reports/, tech stack, placeholders for the live
  demo and repo links
Done when: a fresh clone runs using only the README commands.

[ ] PHASE 9: DEPLOY PREP
Goal: ready to deploy. I will do the account steps myself.
- Frontend: Vercel config with SPA rewrite, VITE_API_URL env
- API: production Dockerfile, CORS origins from env, health
  check; inference via ONNX Runtime or CPU-only torch to
  keep the image small
- DB: DATABASE_URL env (Neon-compatible), migrate + seed
  command for production
- .env.example for every service; no secrets committed
- docs/DEPLOY.md: step-by-step for Vercel + Render + Neon
Done when: the production API image runs locally against the
compose Postgres, and DEPLOY.md is complete.
