# Forecast

Users, orders and events are **SIMULATED**.

Hash `15589597379a864309b5db3ce8e995894c7fa02af58b23848297989141c8faca`. Shared expanding test origins [65, 69, 73]; first four steps scored for every model. Lookback/horizon 12/12; all settings in YAML. Per-series scaling and training windows use observed prefixes only; stockout targets are masked for DL training (observed sales, not latent demand). Validation origin 52 selects epochs, never test scores. LSTM and generic residual N-BEATS covariate/quantile adaptation use seeds [42, 43, 44]; mean metrics across origins, then seed means and sample variance. Baseline rows reproduce Phase 2 (one deterministic seed); their 80% interval calibration is the original 52/56/60 four-step procedure, while serving widths use validation weeks 52–63. WAPE and sMAPE are percentages; MASE and measured P10–P90 coverage are reported even when poor. N-BEATS is not the paper's interpretable configuration. Seed 42 serves; no test-selected ensemble. Small catalog, 78 simulated weeks and pooled intervals limit validity; no real-market accuracy claim.

| Model | Group | Seeds | wape | smape | mase | coverage80 | wape_variance |
| --- | --- | --- | --- | --- | --- | --- | --- |
| seasonal_naive | sku | 1 | 110.18672 | 93.03378 | 1.04802 | 0.93996 | 0.00000 |
| seasonal_naive | category | 1 | 14.74752 | 21.54560 | 0.93329 | 0.27083 | 0.00000 |
| lightgbm | sku | 1 | 97.44225 | 141.71452 | 0.96700 | 0.84007 | 0.00000 |
| lightgbm | category | 1 | 18.95244 | 21.78786 | 1.02756 | 0.12500 | 0.00000 |
| lstm | sku | 3 | 86.70400 | 102.67859 | 0.79547 | 0.89749 | 0.54631 |
| lstm | category | 3 | 30.07033 | 34.84618 | 1.51983 | 1.00000 | 19.65451 |
| nbeats | sku | 3 | 90.32552 | 86.10732 | 0.80553 | 0.86934 | 1.29819 |
| nbeats | category | 3 | 37.58126 | 43.88516 | 1.86870 | 1.00000 | 88.57199 |
