# Model cards

All cards refer to simulated, pseudonymous commerce data and the metrics in `backend/artifacts/evaluation.json`. No real-market generalization is claimed. The active version and fingerprint appear in the protected registry. Customers can withdraw personalization; humans control purchase and inventory decisions.

| Model | Purpose / data / method | Evaluation | Limits / human controls |
| --- | --- | --- | --- |
| Content recommender | Find similar scents. Note/accord/occasion text; TF-IDF 1–2 grams, cosine; cutoff-fitted vocabulary | Temporal Precision/Recall/NDCG@5, coverage, diversity | Metadata quality and similar-family concentration; MMR, filters, admin hide/pin. |
| Item CF | Find related purchases. Aggregated consented order qty, wishlist and weighted activity; item cosine | Same temporal holdout versus popularity | Sparse/new items and feedback bias; new-item content fallback. |
| Hybrid | Personalized discovery. Content/CF/popularity, five validation-weight candidates | Test NDCG 0.3600; CF 0.3642 and popularity 0.1592 in delivered run | Not the best model on every metric; explanations, consent, live eligibility, MMR. |
| Apriori | Cart pairings. Binary historical order baskets; support ≥.004, confidence ≥.08, lift ≥1.05; max 3 items | Support/confidence/lift reported with rules | Association is not causation; hybrid fallback when no rule matches; shoppers decide. |
| Quiz profile | Cold-start suggestions. Explicit answers → eight accord weights; cosine match | Budget/stock/size and bounded-match tests; content holdout is indirect evidence | Match % is alignment, not likelihood. One-off quiz works without consent. |
| Seasonal naive | Weekly benchmark. Same week 52 periods ago; short-history mean fallback | Rolling-origin selection, macro SKU WAPE and eight-week holdout | Two seasonal cycles only, no response to shocks. |
| ETS | Smooth trend/seasonality. Additive damped trend, 13-week season | Same forecast protocol | Season approximation and sparse counts; nonnegative forecasts; human review. |
| SARIMA | Autocorrelation with calendar. (1,0,0)(1,0,0,13), holiday/promo exogenous regressors | Same forecast protocol; failure fallback reported | Short/noisy series and convergence risk; seasonal-naive fallback. |
| LightGBM | Pooled weekly demand. Lags 1/2/4/8/13/52, rolling means/std, SKU/size/product and calendar | Expanding pooled fit, recursive forecast, per-SKU selection, held-out scores | Recursive error accumulation; known calendar only; no future actual features. |
| Croston SBA | Slow/intermittent demand. Positive demand size/inter-arrival smoothing, alpha .15 | Forced for zero fraction >.45 or mean <.8, before holdout | Constant mean forecast, cannot reproduce sharp promo spikes; broad bands. |
| Forecast bands | Decision-support uncertainty. Pooled normalized absolute validation residuals, 80/95 quantiles; extrapolated widening past 4 weeks | Coverage 82.87% / 94.44% on eight-week holdout | Aggregation is conservative, not nominal joint calibration; never promise stock availability. |
| RFM + K-Means | Aggregate segmentation. log(recency/frequency/monetary), standardization, K=3 | Descriptive cluster summaries; no true labels | Labels reflect human interpretation, not known motives; no individual eligibility decisions. |
| Two-tower | Neural showcase. Separate learned tanh user/item towers (12 dims), sampled binary ranking loss | Training learning curve only; optional serving | No independent held-out superiority. Negative samples can include other positives. |
| Session skip-gram | Item2vec-style sequence representation. ±2 item contexts, three negative samples, 12-dimensional embeddings | Training loss/pair count only; optional serving | Short synthetic sequences, false negative sampling, no superiority claim. |
| Latent search | Natural-language product search. TF-IDF + 16-dimensional SVD embeddings, cosine; explicit price/size regex | End-to-end constraint tests and manual query flow | Not an LLM; limited vocabulary, no world knowledge or complex reasoning. |
| Price response | Size-based pricing research. Weekly log(1+units) regression on log(price) plus time | In-sample R², coefficient and weeks | Promo confounding, synthetic prices, no causal elasticity or automated price setting. |
| A/B simulator | Experiment-method demonstration. Seeded random assignment, binomial outcomes, two-proportion z-test | Reproducibility, allocation and bounded p-value tests | Assumed input lift generates outcomes; this does not test the recommender’s actual uplift. |

Forecast selected-system scores: WAPE 62.79%, sMAPE 75.16%, average defined SKU MASE .746. Individual ladder WAPE values are macro SKU averages. Reorder policy uses 95% one-sided normal safety-stock heuristic (`1.645 × recent weekly SD × sqrt(lead)`), not forecast interval quantiles; administrators must review it.

Training validates before fitting and activates only after artifacts/MLflow/database records succeed. Artifacts are trusted local pickle files checked against the manifest checksum; no model-upload endpoint exists. Holiday dates cover 2024–2026, and future unsupported years fail rather than invent lunar holiday dates. Model limitations are exposed both in the product’s Intelligence page and the admin panels.
