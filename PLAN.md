# PLAN.md
Tick [x] when a phase's Done-when checks pass.

## Assumptions
- The user explicitly requested all phases without pauses and Vercel as the deployment target. Do not add Docker or pause between completed phases.
- The phase 6-9 source was published on `complete-phases-real-catalog` at `00b39de`; its file tree exactly matched prepared source `560f2a4`, including the Vercel guard's corrected `date` import. Follow-up commit `2e19249` corrects browser test timing and selectors; `bebe4a5` updates the frontend to the current K=10 metrics and two-tower ablation reports. Original phase commits are retained in `prepared-phase-6-9.bundle` on the recovery branch. Native CI and a Vercel Preview have run against the published source.
- The current reference catalogue has 150 real fragrances across 35 brands and 297 size variants. Prices, stock, users, quizzes, browsing activity, orders and all model-training behaviour are simulated. Product-source links do not verify authenticity or current availability.
- The checked-in evaluation reports use a 52/13/13-week recommender split, 60 auto-drafted search queries with zero human reviews, and three expanding forecast origins. They are pipeline measurements, not customer or commercial performance.
- The public domain serves the verified 35-house / 150-product release. Separate Neon databases are now connected to Preview and Production; the old catalogue database is preserved with a `LEGACY` variable prefix. Production tracks `complete-phases-real-catalog` and uses manual promotion during release checks.
- Phase 9 uses Vercel Services and managed PostgreSQL only. The first correctly configured build completed training but exposed an idle connection shutdown when releasing its session lock. Source `7694dcda` uses a transaction-scoped advisory lock so the direct connection remains active through training and releases safely on commit or rollback. Never reset or overwrite the existing legacy database.
- CI is configured for native PostgreSQL and Playwright. Local tests that need PostgreSQL/browser binaries may be unavailable in this workspace; record which checks actually ran in `reports/verification.md`.
- Hyperparameters are YAML. Data/time splits are chronological. Generated training data and trained weights are not committed.
- The user requested the 35 named houses and a Sephora-inspired shop. All 35 already exist in the reference catalogue; the follow-up refresh exposes them through searchable brand navigation and gives SCENTHAUS its own beauty-retail layout. The storefront source passed full native CI (65 Python tests, four browser journeys, Ruff and frontend build). The final source passed nine native runtime/build-lock/maintenance tests, four browser journeys, Ruff, build and isolated runtime API verification before Production promotion.

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

[x] PHASE 7: REACT UI
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

[x] PHASE 8: DOCS + RESPONSIBLE AI
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

[x] PHASE 9: VERCEL DEPLOY PREP
Goal: deploy and verify the Vercel release with separate Preview and Production databases.
- Frontend: Vercel SPA service with same-origin `/api` calls
- API: FastAPI service, safe build-time setup, CPU ONNX inference,
  CORS origins from env and health check
- DB: managed PostgreSQL URLs, migration and clean-catalogue seed
- `.env.example` files, no secrets committed
- Vercel deployment and verification steps documented
Done when: an isolated Vercel Preview and Production deployment
run against their dedicated clean databases and pass the release
smoke checks in `docs/deployment.md`.

Current release checks complete: Preview source `7694dcda` and Production
source `618a1d1` are Ready and verified against dedicated Neon databases.
Run `37558473333` passed nine native PostgreSQL tests, Ruff, four browser
journeys, the build and isolated runtime-only API checks. Production was
manually promoted; the alias is healthy and semantic search uses the
registered model. Authorized daily maintenance returned 200 in 1.83s.
Hosted guest shopping and access restrictions were checked; privileged
admin/forecast flows were checked in isolated native CI. The portfolio
card and case study are live with the new cover and demo link. Detailed
scope and evidence are in `reports/deployment.md` and
`reports/release-2026-10-06/`.

## Storefront follow-up — 2026-10-07
- User requested faster entry, size selection in Quick add, and shopping UX improvements informed by established perfume retailers.
- Removed the session gate from public pages; bag/account/privacy/quiz/admin wait for their session. Products load independently of optional recommendations, with reserved loading cards and recoverable errors.
- Quick add uses a native modal dialog with size-specific prices, disabled sold-out variants, guarded submission, and bag confirmation. Existing bag quantities are read after session initialization.
- Mobile header/search and card density refreshed within the existing visual system. Same hero re-encoded as WebP (2,117,302 → 162,170 bytes).
- Added browser regressions for a held session, failed recommendation, reconnect, size selection, sold-out state, focus return, mobile width, and a pending existing bag.
- Production build and six local jsdom regression tests pass. Four new browser journeys are present but have not run. Publishing was rejected by automatic approval review for lack of explicit publication authorization; no push or deployment completed. Details: `reports/storefront-2026-10-07.md`.

## 2026-10-07 publishing continuation
- The user authorized cloud-browser publishing, completion and a portfolio update.
- GitHub branch source lacked the account-security extension present in deployed Production `dpl_KeMyxsqHa3z1FZgWGD62nxg8sPZy`. Recovered its account source, migration 0003, tests and dependencies through Vercel Source; copied source was checked against deployment SHA-1 file identifiers (the viewer omits the final newline). No database reset or credential change.
- Combined faster public rendering with the existing size/quantity picker, atomic additive bag endpoint and account security. Fixed consented product-view tracking to wait for session readiness.
- Production and full native CI verification are pending; the public alias remains on the prior deployment until the combined release passes.
