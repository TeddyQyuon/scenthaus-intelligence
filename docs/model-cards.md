# Model cards

Every dataset and metric below uses **SIMULATED** users, orders and events. The fragrance references are real products; their prices, stock, purchase histories and observed demand in this project are not verified market data. These evaluations demonstrate methods and do not establish commercial performance.

| Model | Purpose | Model card |
| --- | --- | --- |
| Recommender | Personalised and cold-start scent discovery | [Recommender](model_cards/recommender.md) |
| Search | Natural-language retrieval over the reference catalogue | [Search](model_cards/search.md) |
| Forecaster | SKU and category demand estimates for admin review | [Forecaster](model_cards/forecaster.md) |

The cards reproduce the metrics in [`ml/reports/`](../ml/reports/). The protected admin view exposes the serving version and method notes. Forecasts and recommendations are decision support; a person remains responsible for purchase and inventory decisions.
