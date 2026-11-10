# SCENTHAUS Intelligence

A fragrance storefront and machine-learning project with recommendations, search, demand forecasting and inventory analytics.

**[Live demo](https://scenthaus-intelligence.vercel.app/)** · [Portfolio case study](https://teddy-qyuon-portfolio.vercel.app/projects/scenthaus-intelligence)

![SCENTHAUS fragrance storefront with product discovery and collection browsing](.github/preview.webp)

## Scope and contribution

An AI-assisted personal project by Wai Yan Hpone Lat, combining a React storefront, a Python API and offline recommendation, search and forecasting pipelines.

- Browse fragrance references with brand and collection filters, search and quick bag actions.
- Explore recommendations, similar scents and natural-language search.
- Review model methods and inventory signals in the protected admin area.
- Use account consent controls, saved items and Stripe test-mode checkout.

Users, historical demand and order behaviour are simulated. Catalogue references do not establish supplier authenticity, stock availability or commercial uplift. The public shop uses a separately verified storefront release; `main` also contains multi-tenant development work. Check [deployment notes](docs/deployment.md) for release boundaries.

## Stack

React, Vite, FastAPI, SQLAlchemy, PostgreSQL, Python, PyTorch, NumPy, ONNX Runtime and Stripe. Vercel hosts the application; training and serving are separate workflows.

## Run locally

Use Python 3.12, Node.js and a new, empty development PostgreSQL database. Create and activate a Python virtual environment, then:

```bash
git clone https://github.com/TeddyQyuon/scenthaus-intelligence.git
cd scenthaus-intelligence
python -m pip install -r backend/requirements-training.txt
npm --prefix frontend ci
```

Copy `backend/.env.example` to `backend/.env` and configure your local database and unique development credentials. From `backend/`, migrate and prepare the development dataset and models:

```bash
alembic upgrade head
python -m app.seed
python -m ml.train_all
python -m uvicorn app.main:app --reload
```

Include the repository root and `backend/` in `PYTHONPATH` for the ML modules. Model preparation can require significant time and memory. Start the frontend in another terminal with `npm --prefix frontend run dev`.

## Checks

```bash
python -m pytest
npm --prefix frontend run test:unit
npm --prefix frontend run build
```

`npm --prefix frontend test` runs browser journeys against a running application. Backend and browser suites require their documented database/model setup; use a disposable test database.

## Evaluation and architecture

Reported evaluation uses generated behaviour and temporal holdouts. It demonstrates the pipelines and their limitations, not real shopper preferences or business performance.

- [Architecture](docs/architecture.md)
- [Model cards](docs/model-cards.md) and [evaluation reports](ml/reports/)
- [Deployment guide](docs/deployment.md)
- [Stripe checkout](docs/stripe-checkout.md)
