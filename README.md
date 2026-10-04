# SCENTHAUS Intelligence

[Live storefront](https://scenthaus-intelligence.vercel.app/) · [Portfolio case study](https://teddy-qyuon-portfolio.vercel.app/projects/scenthaus-intelligence) · [Passed CI run](https://github.com/TeddyQyuon/scenthaus-intelligence/actions/runs/37198738709)

A fragrance storefront and machine-learning pipeline built with **React + Vite + Tailwind (JavaScript/JSX), Python FastAPI and PostgreSQL**. No Next.js. The shopping experience includes a fragrance quiz, product discovery, wishlist, persistent bag, account preferences and a protected business intelligence dashboard.

**All historical customers and orders are simulated.** Products, fragrance houses and bottle imagery are fictional/illustrative. This project demonstrates a reproducible pipeline and modelling methods; it does not establish real commercial uplift or forecast accuracy on real fragrance demand. Demo checkout saves an order and updates inventory without collecting payment.

## Host on Vercel

Deploy this repository **from its root**, with React/Vite and FastAPI in the same Vercel Services project. The root `vercel.json` routes `/api/*` to Python and all storefront routes to React. No Docker host is required. PostgreSQL is a dedicated managed database, for example Neon through Vercel Marketplace.

1. Import `TeddyQyuon/scenthaus-intelligence` into the Qyuon Vercel team; keep Root Directory at the repository root.
2. Create a **dedicated** PostgreSQL database and set the environment variables below. Do not reuse another application's database.
3. Deploy. The Python build migrates and initializes the database once, then registers the included checksum-verified trained model. Later builds preserve customers, orders and admin catalogue changes.
4. Visit `/api/health`, `/shop`, `/quiz` and `/admin`; sign in at `/account` using your configured admin account. Demo checkout records an order without charging money.

| Environment variable | Value |
| --- | --- |
| DATABASE_URL | Dedicated PostgreSQL connection URL with `sslmode=require`; a pooled Neon URL works. |
| DATABASE_URL_UNPOOLED | Direct PostgreSQL URL for the initialization lock when DATABASE_URL uses a transaction pooler; injected by the Neon integration. |
| ENVIRONMENT | `production` |
| SECRET_KEY | Unique random secret of at least 32 characters. |
| ADMIN_EMAIL | Your admin email, default `admin@scenthaus.demo`. |
| ADMIN_PASSWORD | Your chosen password, at least 12 characters, used only for initial seeding. |
| CRON_SECRET | Unique random secret for authenticated maintenance. |
| ALLOWED_ORIGINS | Your exact HTTPS production origin; Vercel also injects the current deployment and production hosts. |

Keep secrets in Vercel environment variables, never in Git. The daily Vercel Cron runs retention and reconciles complete forecast weeks at 04:00 Singapore time. Serverless requests load the committed model and do not train or write model files.

Scheduled training runs separately through `.github/workflows/retrain.yml` at 03:00 Sundays in Singapore. Enable it only after configuring repository secrets `SCENTHAUS_DATABASE_URL`, `SCENTHAUS_SECRET_KEY`, `SCENTHAUS_ADMIN_PASSWORD` and variable `SCENTHAUS_RETRAIN_ENABLED=true`. It validates/evaluates, records MLflow evidence, commits model artifacts and lets the Git integration redeploy Vercel. That schedule is provided but is **not activated by this source alone**.

The full training dependencies remain in `backend/requirements.txt`. Vercel uses the smaller runtime dependencies in `backend/pyproject.toml` and serves precomputed forecasts; LightGBM, statsmodels, Apriori training and MLflow are outside the request runtime.

Public deployment status is recorded in [deployment evidence](reports/deployment.md). A READY static build alone does not establish that the API or database works.

## Optional local containers

Docker Compose remains an optional local convenience, not the requested hosting platform. Copy `.env.example` to `.env`, choose `POSTGRES_PASSWORD`, `SECRET_KEY` and `ADMIN_PASSWORD`, then run `docker compose up --build`. Storefront: http://localhost:5173; API: http://localhost:8000. The initializer generates and trains simulated history; the worker runs locally.

## Run without Docker

Use Python 3.12+, Node 22+ and a running PostgreSQL database.

```bash
cd backend
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
cp .env.example .env
# Set DATABASE_URL and your ADMIN_PASSWORD in backend/.env.
alembic upgrade head
python -m app.seed
python -m app.ml.train
uvicorn app.main:app --reload --port 8000
```

In a second terminal:

```bash
cd frontend
npm ci
npm run dev
```

Optional worker: from backend with its environment active, run `python -m app.worker`. MLflow tracking uses a local SQLite store by default; open it with a compatible MLflow UI installation or inspect the logged metrics/artifacts. `mlflow-skinny` supplies tracking APIs, not the full UI server.

## What is implemented

| Area | Features |
| --- | --- |
| Data | Product note pyramids, accords, concentration, occasions/seasons, gender labels, longevity/sillage, 30/50/100ml variants, stock; SQL events, wishlist, bag and quiz; seeded users/orders with hidden tastes, noise, trend and Singapore calendar spikes; validation gates every training run. |
| Recommendations | Precomputed TF-IDF/cosine similarities; item-item CF from orders/wishlist/activity; Apriori basket rules; quiz accord weights with match percentage; validation-tuned hybrid and new-item content fallback; shared-note/wishlist explanations; budget/size/gender/season/stock filters; MMR with brand penalty; in-stock substitutes; session-informed home row. |
| Forecasts | Weekly SKU, brand and family aggregation; 4–12 week horizon; seasonal naive, ETS, SARIMA and pooled LightGBM; Croston for sparse SKUs; three expanding validation origins; WAPE/sMAPE/MASE; 80/95% residual-calibrated bands; holiday/promo regressors; revenue, trend, safety stock, reorder point, suggested quantities; holdout and live snapshots. |
| Admin | API-protected dashboard, date-filtered KPIs/CSV, sales/forecast bands, top products/houses/size mix, stock risk, RFM + K-Means segments, placement attribution, evaluation, experiment simulator, model versions, latency/error/PSI monitoring, pin/hide and audited stock edits. |
| Evaluation & operations | Temporal recommendation holdout and popularity baseline; random A/B assignment and two-proportion significance; Compose, Alembic, MLflow tracking, atomic activation, scheduled retraining, pytest, Playwright journeys and GitHub Actions with native PostgreSQL. |
| Responsible AI | Default-off personalization, withdrawal and data download, no account email/password in model features, per-model cards, recommendation explanations, human overrides and documented risk/involvement. |
| Stretch | Natural language search using learned TF-IDF/SVD latent embeddings; NumPy two-tower network; item2vec-style skip-gram session embeddings; observational log-price response by size. Experimental routes are opt-in and carry no superiority/causality claim. |

See [feature matrix](docs/feature-matrix.md) for individual A–G mappings, [architecture](docs/architecture.md), [model cards](docs/model-cards.md) and [governance](docs/governance.md).

## Reproduced results

Seed 42 produced **2,000 simulated customers, 12,139 orders, 90,495 events, 36 products and 108 SKUs**, from 2024-09-30 through 2026-09-27. Hidden taste vectors are used only to generate the data; they are not provided to the models. Four new products launch in the final week. Genuine test interactions therefore exclude products not available at the cutoff.

Recommendation evaluation uses the last eight weeks as test and the preceding eight as validation. It excludes previously purchased products from both ranking candidates and relevant targets, evaluates 504 users with novel held-out purchases, and uses 32 available candidate products. Weights are chosen on validation NDCG, never on the test set. The table evaluates rankers before serving filters/MMR.

| Ranker | Precision@5 | Recall@5 | NDCG@5 | Coverage | Diversity |
| --- | ---: | ---: | ---: | ---: | ---: |
| Popularity baseline | 0.0687 | 0.2345 | 0.1592 | 0.5313 | 0.7059 |
| Content | 0.1405 | 0.5134 | 0.3573 | 1.0000 | 0.6531 |
| Collaborative filtering | 0.1405 | 0.5187 | 0.3642 | 1.0000 | 0.6538 |
| Tuned hybrid | 0.1413 | 0.5154 | 0.3600 | 1.0000 | 0.6527 |

CF has the best NDCG in this run; the hybrid is not universally superior. Coverage measures the fraction of available items ever recommended; diversity is mean pairwise cosine distance. Simulation design can favour particular methods, so these scores should not be used as real-market performance claims.

Forecast models are selected per SKU using three rolling origins, each with a four-week validation horizon. An untouched eight-week holdout reports **62.79% volume-weighted WAPE**, **75.16% sMAPE** and **0.746 mean per-SKU MASE**. WAPE is undefined when actual demand is zero; MASE is undefined for a constant history and is omitted from the average. New/slow SKUs are difficult and handled separately.

| Interval | Nominal | Measured holdout coverage |
| --- | ---: | ---: |
| 80% band | 80% | 82.87% |
| 95% band | 95% | 94.44% |

Intervals use pooled normalized validation residuals and widen beyond the calibrated four-week horizon. Aggregate bands sum SKU bounds and are conservative, **not nominally calibrated joint intervals**. Revenue forecasts use current list prices; the admin sales KPI/chart uses actual transaction prices. The selected-model WAPE is volume weighted; individual ladder scores shown in the dashboard are macro SKU averages and must not be compared as identical metrics.

Training diagnostics for the neural experiments are saved in `backend/artifacts/evaluation.json`; they are not independent recommendation evaluations. Price-response coefficients are promotion-confounded and noncausal. A/B conversions are sampled from user-entered rates, not actual measured recommender uplift. Validation on a public retail dataset is optional future work and has not been performed.

## Checks and evidence

```bash
cd backend
python -m pytest tests -q
python benchmark.py
cd ../frontend
npm run build
npx playwright install chromium
# Start the API and Vite before running locally:
npx playwright test
```

The delivered evaluation JSON and training log contain actual run results. [Verification report](reports/verification.md) separates local, CI and live evidence. [GitHub CI run 37198738709](https://github.com/TeddyQyuon/scenthaus-intelligence/actions/runs/37198738709) passed **30 Python tests against native PostgreSQL 16**, including concurrent checkout, **three Playwright journeys**, and the frontend build. It regenerates and trains the simulated dataset before testing. Production browser checks passed for the homepage, wishlist/cart reloads, quiz, demo checkout, consent withdrawal and guest admin gate. [Production API smoke results](reports/production-api-smoke.json) record 17 successful checks, including authenticated forecasting, inventory, exports and model health. These smoke checks do not establish concurrent production capacity or an internet latency under 200 ms.

## API

Session establishment: `GET /auth/session` returns a CSRF token and an opaque HttpOnly session cookie. All mutations require the cookie, the returned `X-CSRF-Token` and an allowlisted Origin. Accounts use Argon2 password hashes; login/register rotate sessions. All admin and forecast routes enforce the admin role in Python.

| Endpoint | Purpose |
| --- | --- |
| GET /recommend/similar?product_id=1 | Nearby scents |
| GET /recommend/also-bought?product_id=1 | Item CF |
| GET /recommend/user | Hybrid preferences; optional experiment=two_tower/item2vec |
| POST /recommend/quiz | mood, occasion, intensity, budget and optional size |
| GET /recommend/cart | Basket association rules, hybrid fallback |
| GET /recommend/substitutes?product_id=7 | In-stock alternatives |
| GET /forecast/sku?sku=SH-001-50&horizon=8 | Admin-only SKU forecast |
| GET /forecast/summary?group=brand&key=Atelier%2008 | Admin-only aggregate |
| POST /events | Consented view/impression/click; minted recommendation references for attribution |
| GET /search?q=fresh%20office%20scent%20under%20$150 | Latent semantic search with price/size constraints |

Catalogue, wishlist, bag, orders, consent/export and admin endpoints appear in development OpenAPI. A quiz match % is cosine accord alignment, not a probability of liking the fragrance. Stock and visibility are checked live, while static content/CF similarities are precomputed and cached. Checkout locks the user row, checks a unique idempotency key and conditionally decrements stock in one transaction.

## Deployment

[Deployment guide](docs/deployment.md) explains the Vercel Services topology, hosted PostgreSQL setup, immutable trained artifacts and separate training jobs. The frontend and Python API share the same HTTPS origin. The existing Docker/Render/Railway files remain optional alternatives and are not used for Vercel hosting.

## References

- [FastAPI](https://fastapi.tiangolo.com/), [SQLAlchemy](https://docs.sqlalchemy.org/en/20/orm/quickstart.html), [Vite](https://vite.dev/guide/)
- [TF-IDF](https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html), [LightGBM](https://lightgbm.readthedocs.io/en/stable/Python-API.html), [MLflow tracking](https://mlflow.org/docs/latest/ml/tracking/)
- [Singapore 2026 holidays, MOM](https://www.mom.gov.sg/newsroom/press-releases/2025/0616-public-holidays-for-2026) and [2027 holidays, MOM](https://www.mom.gov.sg/newsroom/press-releases/2026/0618-public-holidays-for-2027). Calendar dates cover 2024–2027; unknown future years fail until verified dates are added.
- [Singapore Model AI Governance Framework, IMDA](https://www.imda.gov.sg/-/media/imda/files/infocomm-media-landscape/sg-digital/tech-pillars/artificial-intelligence/second-edition-of-the-model-ai-governance-framework-22jan.pdf)
- [Vercel Vite deployment](https://vercel.com/docs/frameworks/frontend/vite), [external rewrites](https://vercel.com/docs/routing/rewrites), [Render Blueprint](https://render.com/docs/blueprint-spec), [Compose startup order](https://docs.docker.com/compose/how-tos/startup-order/)
