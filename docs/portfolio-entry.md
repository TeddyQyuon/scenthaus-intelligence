# SCENTHAUS Intelligence

**A fragrance discovery storefront with a real reference catalogue and an end-to-end machine-learning evaluation and serving pipeline.**

- Built a React/Vite storefront and FastAPI/PostgreSQL service for product discovery, consent-aware recommendations, search, simulated checkout and admin forecasting. The storefront includes a searchable 35-house brand directory, direct brand filters and a beauty-retail layout.
- Evaluated recommender, search and demand models against baselines using chronological splits; the reported user activity, sales and search labels are simulated or unreviewed.
- Prepared Vercel Services deployment with versioned serving artifacts, API guards and a catalog release check. The current public Vercel alias still serves the older invented-catalog build.

## Selected results

These results come from generated activity and demand, not a retailer's customer or sales data.

| Task | Result | Context |
| --- | --- | --- |
| Recommendations | Item CF NDCG@10 0.13731; full two-tower 0.13405 | 1,058 users, same 52/13/13-week split; two-tower result uses one seed |
| Search | Hybrid MRR@10 0.95278, NDCG@10 0.93623 | 60 draft queries; 0 human-reviewed labels |
| SKU forecast | LSTM WAPE 86.70%, MASE 0.795 | Mean of 3 seeds across 3 test origins; first 4 steps scored |
| Category forecast | Seasonal-naive WAPE 14.75%, MASE 0.933 | Baseline outperformed both neural methods on category WAPE and MASE |

The recommender and forecasting models do not win every comparison. Category forecast interval coverage is poor for the baselines and over-wide for the neural models. Full protocols and limits appear in [model cards](model-cards.md) and [`ml/reports/`](../ml/reports/).

## Stack

React, Vite, React Router, Recharts, FastAPI, SQLAlchemy, PostgreSQL, PyTorch for offline training, NumPy/ONNX Runtime for serving, Hugging Face MiniLM, MLflow and Vercel Services.

## Links

- Repository: [github.com/TeddyQyuon/scenthaus-intelligence](https://github.com/TeddyQyuon/scenthaus-intelligence)
- Portfolio page: [SCENTHAUS Intelligence case study](https://teddy-qyuon-portfolio.vercel.app/projects/scenthaus-intelligence)
- Current demo domain: [scenthaus-intelligence.vercel.app](https://scenthaus-intelligence.vercel.app/) — this currently serves the previous invented-catalog release, not this source revision.
- Deployment evidence: [`reports/deployment.md`](../reports/deployment.md)
