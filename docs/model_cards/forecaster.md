# Model card: demand forecasts

## Intended use

Estimate future weekly units by SKU and category for a protected admin dashboard. The dashboard supports review of inventory risk; the model does not place orders, change supplier commitments or guarantee product availability.

## Data and method

All orders, stock histories and resulting demand series are **SIMULATED**. The current snapshot has 78 weeks, 150 products and 297 size variants. Actual recorded sales can be censored by simulated stockouts, so they are not latent demand.

Seasonal-naive and LightGBM baselines and the LSTM/N-BEATS models share expanding test origins 65, 69 and 73. Only the first four forecast weeks are scored at each origin. The learned models use seeds 42, 43 and 44; the table reports their seed means. Baselines use one deterministic seed. LSTM and N-BEATS return learned P10/P50/P90 quantiles. Baseline ranges are calibrated from validation residuals. Coverage is the fraction of actual values inside the nominal 80% band.

## Results

WAPE and sMAPE are percentages; MASE is unitless.

| Model | Group | WAPE | sMAPE | MASE | 80% interval coverage |
| --- | --- | ---: | ---: | ---: | ---: |
| Seasonal naive | SKU | 110.19% | 93.03% | 1.048 | 94.00% |
| LightGBM | SKU | 97.44% | 141.71% | 0.967 | 84.01% |
| LSTM | SKU | 86.70% | 102.73% | 0.795 | 89.75% |
| N-BEATS | SKU | 90.33% | 86.11% | 0.806 | 86.93% |
| Seasonal naive | Category | 14.75% | 21.55% | 0.933 | 27.08% |
| LightGBM | Category | 18.95% | 21.79% | 1.028 | 12.50% |
| LSTM | Category | 30.07% | 34.84% | 1.519 | 100.00% |
| N-BEATS | Category | 37.58% | 43.89% | 1.869 | 100.00% |

The LSTM has the lowest SKU WAPE in this run. Seasonal naive is stronger than both neural models on category WAPE and MASE. Category interval coverage is poor for the baselines and over-wide for the neural models.

## Limits and controls

- Seventy-eight generated weeks and a small catalogue cannot represent real promotions, supply delays, product launches or market shocks.
- Four scored steps at three test origins do not verify the full 12-week horizon.
- The nominal interval coverage varies substantially by model and aggregation level; it must not be treated as a calibrated service guarantee.
- The admin dashboard shows the selected model, historical error and interval bands. Inventory actions remain under human review.

Full protocol and results: [`ml/reports/forecast.md`](../../ml/reports/forecast.md).
