# Baselines

Users, orders and events are **SIMULATED**.

Hash `15589597379a864309b5db3ce8e995894c7fa02af58b23848297989141c8faca`. Train/validation/test: 52/13/13 weeks, exclusive cutoffs 2026-03-30 / 2026-06-29 / 2026-09-28. K=10; novel purchase targets; no future wishlist/event signals. CF uses orders and wishlists/events. Hybrid weights [0.2, 0.7, 0.1] selected on validation only. BM25 is implemented and tested; query-quality evaluation is deferred to the manually reviewable labels in Phase 4. Forecast origins [65, 69, 73], 4-week horizon; rolling origins refit on observed prefixes. WAPE/sMAPE in percent, MASE uses 52-week seasonal scale (fallback lag 1 only for short histories), coverage of validation-residual 80% intervals. SKU and category scores are separate, not double counted; intervals pooled across heterogeneous series may be poorly calibrated. Zero-demand WAPE and constant-history MASE are undefined, never reported as zero error.

| Task | Model | precision | recall | ndcg | mrr | coverage | brand_diversity | users | wape | smape | mase | coverage80 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| recommend | popularity | 0.03195 | 0.18188 | 0.10609 | 0.10262 | 0.15068 | 0.35624 | 1058.00000 | undefined | undefined | undefined | undefined |
| recommend | cf | 0.03781 | 0.21331 | 0.13731 | 0.13695 | 0.97260 | 0.79026 | 1058.00000 | undefined | undefined | undefined | undefined |
| recommend | content | 0.02420 | 0.13533 | 0.08460 | 0.08660 | 0.28082 | 0.23913 | 1058.00000 | undefined | undefined | undefined | undefined |
| recommend | hybrid | 0.03696 | 0.20821 | 0.13679 | 0.13715 | 0.94521 | 0.81786 | 1058.00000 | undefined | undefined | undefined | undefined |
| sku forecast | seasonal_naive | undefined | undefined | undefined | undefined | undefined | undefined | undefined | 110.18672 | 93.03378 | 1.04802 | 0.93996 |
| category forecast | seasonal_naive | undefined | undefined | undefined | undefined | undefined | undefined | undefined | 14.74752 | 21.54560 | 0.93329 | 0.27083 |
| sku forecast | lightgbm | undefined | undefined | undefined | undefined | undefined | undefined | undefined | 97.44225 | 141.71452 | 0.96700 | 0.84007 |
| category forecast | lightgbm | undefined | undefined | undefined | undefined | undefined | undefined | undefined | 18.95244 | 21.78786 | 1.02756 | 0.12500 |
