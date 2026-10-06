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

| Executed local check | Result |
| --- | --- |
| Full pytest suite | 58 passed, 1 native-Postgres-only concurrency test skipped |
| Ruff / Git whitespace check | Clean |
| React production build | Passed |
| Exclusive fixture writer test | Passed |
| API / Vite / MLflow health | HTTP 200 / 200 / 200 |
| MLflow HTTP experiment query | Finished baseline, recommender, search and forecast runs visible |

Failed development runs remain in MLflow; an invalid `@` metric-name integration was corrected and search rerun. The phase report metrics come from completed evaluations, never from fabricated success values.
