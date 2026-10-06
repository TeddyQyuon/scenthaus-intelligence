# Recommender

Users, orders and events are **SIMULATED**.

Same exclusive 52/13/13-week split, K=10, novel purchase targets and eligible catalog as baselines. Actual PyTorch two towers with frozen MiniLM revision `c9745ed1d9f207416be6d2e6f8de32d1f16199bf`, ID/recent item/quiz features; purchase > cart > wishlist > view weights. Random/popular/content-hard negatives exclude known positives; duplicate in-batch positives masked. Validation NDCG selects early-stopped epoch count, refit through validation before untouched test. Ablations remove the indicated inputs; BPR is a loss ablation. Final serving cache refits through all observed data. Cosine match is an alignment score, not calibrated preference probability. One recommender seed; small catalog and coarse curated accords limit validity. No commercial uplift claim. Results include baselines even if the neural model loses.

| Model | precision | recall | ndcg | mrr | coverage | brand_diversity | users |
| --- | --- | --- | --- | --- | --- | --- | --- |
| popularity | 0.03195 | 0.18188 | 0.10609 | 0.10262 | 0.15068 | 0.35624 | 1058 |
| cf | 0.03781 | 0.21331 | 0.13731 | 0.13695 | 0.97260 | 0.79026 | 1058 |
| content | 0.02420 | 0.13533 | 0.08460 | 0.08660 | 0.28082 | 0.23913 | 1058 |
| hybrid | 0.03696 | 0.20821 | 0.13679 | 0.13715 | 0.94521 | 0.81786 | 1058 |
| two_tower:full | 0.03743 | 0.21113 | 0.13405 | 0.13352 | 0.60959 | 0.75208 | 1058 |
| two_tower:no_content | 0.03280 | 0.19144 | 0.12450 | 0.12696 | 0.78767 | 0.79565 | 1058 |
| two_tower:no_history | 0.03384 | 0.19722 | 0.13339 | 0.13828 | 1.00000 | 0.80435 | 1058 |
| two_tower:no_quiz | 0.03620 | 0.20270 | 0.12835 | 0.12537 | 0.64384 | 0.71815 | 1058 |
| two_tower:bpr | 0.03894 | 0.22532 | 0.14087 | 0.13754 | 0.71233 | 0.64216 | 1058 |
