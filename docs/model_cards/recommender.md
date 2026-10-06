# Model card: fragrance recommendations

## Intended use

Rank fragrances for discovery, including recommendations from consented interaction history and one-time quiz answers. Shoppers decide what to open or place in the demo bag. The model is not a measure of fragrance quality or a prediction that someone will like or buy an item.

## Data and method

All behavioural records are **SIMULATED**. The evaluation snapshot contains 2,000 generated users and 78 weeks of activity/orders across 150 reference products and 297 size variants. Training uses orders, wishlists and events only for users who have opted in; identifiers are pseudonymous. Non-consented quiz answers are used for that response only and are not stored.

The full two-tower model combines user/item identifiers, recent items, quiz accords, and fragrance metadata/text features. Baselines and neural variants use the same chronological 52/13/13-week split, eligible catalogue and 1,058 test users; targets are novel purchases and K=10. The full model uses one training seed in this reported run. The BPR row is a loss ablation, not the default serving model.

## Results

| Model | Precision@10 | Recall@10 | NDCG@10 | Coverage | Brand diversity |
| --- | ---: | ---: | ---: | ---: | ---: |
| Popularity | 0.03195 | 0.18188 | 0.10609 | 0.15068 | 0.35624 |
| Item CF | 0.03781 | 0.21331 | 0.13731 | 0.97260 | 0.79026 |
| Hybrid | 0.03696 | 0.20821 | 0.13679 | 0.94521 | 0.81786 |
| Two-tower, full | 0.03743 | 0.21113 | 0.13405 | 0.60959 | 0.75208 |
| Two-tower, BPR ablation | 0.03894 | 0.22532 | 0.14087 | 0.71233 | 0.64216 |

The full two-tower model is below item CF. The BPR ablation has the highest NDCG in this run, but its single-seed result does not establish a consistent improvement over that baseline.

## Limits and controls

- Synthetic tastes, limited history, curated metadata and a 150-product catalogue do not establish behaviour on a real retailer's customers or inventory.
- A cosine quiz match is an alignment score, not a probability of satisfaction.
- Explanations name shared notes/accords or basket associations; these are descriptive signals, not causal reasons.
- Personalisation is off by default. Users can withdraw consent; this removes their event/profile/recommendation records and excludes their activity from future training. Existing model aggregates update only when models are retrained.
- Eligibility filters, stock display, brand-diversity ranking and human-controlled product hide/pin settings constrain the results. No purchase is automatic.

Full metrics and the evaluation protocol: [`ml/reports/recommender.md`](../../ml/reports/recommender.md).
