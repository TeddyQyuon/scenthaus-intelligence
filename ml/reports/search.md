# Search

Users, orders and events are **SIMULATED**.

Actual frozen all-MiniLM-L6-v2, BM25 and reciprocal-rank fusion (constant 60), same 60 draft queries, same live SQL budget/size/gender/season/in-stock constraints. Labels are catalog-rule drafts, **manual review required**; these scores test a pipeline and do not establish real user relevance. Catalog text and label wording overlap, favoring lexical search. Query vectors cache 128 entries; product vectors precomputed. No behavioural random split or customer text is used. Hyperparameters: ml/configs/search.yaml.

| model | MRR@10 | NDCG@10 | queries | reviewed |
| --- | --- | --- | --- | --- |
| bm25 | 0.93889 | 0.93562 | 60 | 0 |
| dense | 0.92183 | 0.88918 | 60 | 0 |
| hybrid | 0.95278 | 0.93623 | 60 | 0 |
