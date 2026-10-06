# Tracking and serving

Users, orders and events are **SIMULATED**.

| Check | Evidence |
| --- | --- |
| Input validation | Every training entrypoint validates the DB snapshot before opening a run |
| Dataset version | Catalog/order hash plus consented quiz, wishlists, events and stock weeks |
| Experiment tracking | MLflow SQLite backend; params, numerical metrics, YAML, runtime and reports |
| Model checkpoints | Actual Torch checkpoints retained as MLflow artifacts, ignored by Git |
| Serving release | Immutable version folder; SHA-256 for bundle, search/tower caches and metadata |
| Activation | Complete manifest validation, fsync and atomic current.json replacement |
| Rollback | Explicit operator command; checksum and path tests reject corrupted/outside files |
| Native stack | scripts/dev.py starts API, Vite and MLflow; managed Postgres configured separately |
| Schedule | Optional weekly simulated fixture training; artifacts retained, no automatic production activation |

Cross-platform numerical equality is not promised. Fixed seeds, pinned encoder revision and runtime/input-array checksums make differences reviewable. Cached serving refits on all observed history; report metrics remain from earlier untouched test windows. A local PGlite fixture is serialized by an exclusive lock and is not evidence of concurrent native PostgreSQL correctness. Live error reconciliation and drift monitoring are operational heuristics rather than guarantees.

The following local results are historical Phase 6 evidence. Current native PostgreSQL and browser release checks are recorded in [`reports/verification.md`](../../reports/verification.md).

| Historical local check | Result |
| --- | --- |
| Full pytest suite | 58 passed, 1 native-Postgres-only concurrency test skipped |
| Ruff / Git whitespace check | Clean |
| React production build | Passed |
| Exclusive fixture writer test | Passed |
| API / Vite / MLflow health | HTTP 200 / 200 / 200 |
| MLflow HTTP experiment query | Finished baseline, recommender, search and forecast runs visible |

Failed development runs remain in MLflow; an invalid `@` metric-name integration was corrected and search rerun. The phase report metrics come from completed evaluations, never from fabricated success values.

Native release CI on source `2e19249` completed actual baseline, recommender, search and three-seed forecast training, then passed all 65 Python tests with zero skips and Ruff. The training artifact is `11389448639` from run `37411420198`; its serving version is `20261006T040911-15589597-827c10a1` with data hash `15589597379a864309b5db3ce8e995894c7fa02af58b23848297989141c8faca`. Its four tracked training receipts identify that exact source and dataset. This run's browser stage exposed stale metric fields in frontend panels; it is not an aggregate CI success. The corrected frontend is verified separately against this immutable bundle, as recorded in the current verification report.
