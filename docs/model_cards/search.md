# Model card: natural-language fragrance search

## Intended use

Retrieve reference fragrances from short natural-language queries, then apply the catalogue's price, size, gender, season and in-stock filters. Search is an exploratory aid; the query labels and displayed availability do not establish what a shopper will prefer or what a retailer can supply.

## Data and method

The product references are real; activity, prices, stock and all evaluation labels are **SIMULATED** or curated for this project. The test contains 60 draft queries. Labels are generated from catalogue rules and overlap with catalogue text. None has been reviewed by a human. The pipeline compares BM25 lexical retrieval, dense all-MiniLM-L6-v2 vectors, and reciprocal-rank fusion of the two. Query vectors use an in-memory cache of up to 128 entries; query text is not used to train the ranking model.

The Vercel runtime uses a pinned, quantized ONNX encoder. It does not run model training or download encoder weights during a request.

## Results

| Method | MRR@10 | NDCG@10 | Draft queries | Human-reviewed |
| --- | ---: | ---: | ---: | ---: |
| BM25 | 0.93889 | 0.93562 | 60 | 0 |
| Dense | 0.92183 | 0.88918 | 60 | 0 |
| Hybrid reciprocal-rank fusion | 0.95278 | 0.93623 | 60 | 0 |

These numbers measure agreement with the draft labels, not real shopper relevance. The label construction and shared product/query terms can favour lexical matching.

## Limits and controls

- There is no independent human relevance set or behavioural search evaluation.
- Catalogue text, notes and editorial labels can be incomplete or inconsistent.
- Search results apply current demo stock and product visibility from PostgreSQL; those values are simulated.
- A shopper can adjust filters or inspect product details. Search has no checkout or pricing authority.

Full protocol and results: [`ml/reports/search.md`](../../ml/reports/search.md).
