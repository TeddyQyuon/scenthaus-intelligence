# Recommender

Users, orders and events are **SIMULATED**.

Same exclusive 52/13/13-week split, K=10, novel purchase targets and eligible catalog as baselines. Actual PyTorch two towers with frozen MiniLM revision `c9745ed1d9f207416be6d2e6f8de32d1f16199bf`, ID/recent item/quiz features; purchase > cart > wishlist > view weights. Random/popular/content-hard negatives exclude known positives; duplicate in-batch positives masked. Validation NDCG selects early-stopped epoch count, refit through validation before untouched test. Ablations remove the indicated inputs; BPR is a loss ablation. Final serving cache refits through all observed data. Cosine match is an alignment score, not calibrated preference probability. One recommender seed; small catalog and coarse curated accords limit validity. No commercial uplift claim. Results include baselines even if the neural model loses.

| Model | precision | recall | ndcg | mrr | coverage | brand_diversity | users |
| --- | --- | --- | --- | --- | --- | --- | --- |
| popularity | 0.03195 | 0.18188 | 0.10609 | 0.10262 | 0.15068 | 0.35624 | 1058 |
| cf | 0.03781 | 0.21331 | 0.13731 | 0.13695 | 0.97260 | 0.79026 | 1058 |
| content | 0.02420 | 0.13533 | 0.08460 | 0.08660 | 0.28082 | 0.23913 | 1058 |
| hybrid | 0.03696 | 0.20821 | 0.13679 | 0.13715 | 0.94521 | 0.81786 | 1058 |
| two_tower:full | 0.03743 | 0.21113 | 0.13407 | 0.13354 | 0.60959 | 0.75198 | 1058 |
| two_tower:no_content | 0.03488 | 0.19291 | 0.13313 | 0.14305 | 1.00000 | 0.84622 | 1058 |
| two_tower:no_history | 0.03563 | 0.20386 | 0.13646 | 0.14213 | 0.91096 | 0.76304 | 1058 |
| two_tower:no_quiz | 0.03516 | 0.19773 | 0.12979 | 0.13070 | 0.60274 | 0.71720 | 1058 |
| two_tower:bpr | 0.03894 | 0.22532 | 0.14087 | 0.13754 | 0.71233 | 0.64216 | 1058 |
