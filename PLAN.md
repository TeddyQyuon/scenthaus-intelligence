# PLAN.md
Tick [x] when a phase's Done-when checks pass.

## Assumptions
- The user explicitly requested all phases without pauses and Vercel as the deployment target. Do not add Docker or pause between completed phases.
- The working source is the real-catalogue branch based on phase 6 commit `215eb33`; the phase 7-9 implementation is committed locally as `f3ec1dc`. It has not reached GitHub: shell Git has no CLI credential and the connected GitHub integration rejected repository writes. The remote feature branch remains at phase 5 (`bdc7653`), so its CI and Vercel preview have not run for this source.
- The current reference catalogue has 150 real fragrances across 35 brands and 297 size variants. Prices, stock, users, quizzes, browsing activity, orders and all model-training behaviour are simulated. Product-source links do not verify authenticity or current availability.
- The checked-in evaluation reports use a 52/13/13-week recommender split, 60 auto-drafted search queries with zero human reviews, and three expanding forecast origins. They are pipeline measurements, not customer or commercial performance.
- The current public Vercel alias still returns the older invented catalogue. The Vercel project has database integration variables scoped to Production; the latest feature-branch Preview could not initialize without `DATABASE_URL`. The release guard refuses to change a database whose catalogue is not the exact 150-product release.
- Phase 9 uses Vercel Services and managed PostgreSQL only. A separate empty Preview database and a separate empty Production database are required before first deployment; account configuration remains the owner's step. Never reset or overwrite the existing production database as part of this work.
- CI is configured for native PostgreSQL and Playwright. Local tests that need PostgreSQL/browser binaries may be unavailable in this workspace; record which checks actually ran in `reports/verification.md`.
- Hyperparameters are YAML. Data/time splits are chronological. Generated training data and trained weights are not committed.

## Phases

[x] PHASE 0: SCAFFOLD
Goal: a monorepo that runs end to end with empty features.
- frontend/: React + Vite + React Router
- backend/: FastAPI, SQLAlchemy, Alembic, GET /health
- ml/ (package, configs/, reports/) and data/
- Native local processes plus Vercel service configuration; no Docker requirement
- ruff config, pytest in backend and ml, .gitignore, git init
- Fill in the Commands section of AGENTS.md
Done when: the frontend and /health run through the documented
local process setup, and tests + lint pass.

[x] PHASE 1: DATA
Goal: realistic simulated data in Postgres + event logging.
- Tables: products, users (with quiz_profile), events, orders,
  order_items, stock
- Seed 150 real fragrance references across 35 brands:
  concentration, top/heart/base notes,
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

[x] PHASE 4: SEMANTIC SEARCH
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

[x] PHASE 5: DL FORECASTING
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

[x] PHASE 6: TRACKING + SERVING
Goal: reproducible runs and a one-command stack.
- MLflow tracking in every training script: params, metrics,
  artifacts, dataset version hash
- Versioned model folders with a current.json pointer and a
  rollback script
- API loads the current models at startup and returns the
  model version in responses
- Local optional MLflow tracking; Vercel build-time artifact generation
Done when: the native local process setup serves a verified
versioned model and a training run appears in MLflow.

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

[ ] PHASE 9: VERCEL DEPLOY PREP
Goal: prepare a Vercel-only release; the owner handles database and account setup.
- Frontend: Vercel SPA service with same-origin `/api` calls
- API: FastAPI service, safe build-time setup, CPU ONNX inference,
  CORS origins from env and health check
- DB: managed PostgreSQL URLs, migration and clean-catalogue seed
- `.env.example` files, no secrets committed
- Vercel deployment and verification steps documented
Done when: an isolated Vercel Preview and Production deployment
run against their dedicated clean databases and pass the release
smoke checks in `docs/deployment.md`.

Current blocker: the public alias still serves the prior invented
catalogue and database variables are Production-only. The owner
must configure new empty Preview and Production databases before
this phase can be checked complete. The locally committed source
must also be pushed to the feature branch before CI or Vercel can
verify it.
