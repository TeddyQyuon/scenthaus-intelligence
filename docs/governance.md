# Human involvement and risk

This project uses Singapore’s Model AI Governance Framework as a design lens: internal accountability, proportionate human involvement, operations management and transparent stakeholder communication. This document describes engineering choices, not a PDPA compliance opinion or certification.

| Decision | Involvement | Reason and control |
| --- | --- | --- |
| Suggested fragrances | Human-over-the-loop | Low-stakes discovery; shoppers choose what to open/buy. Match explanations, opt-out, filters and brand diversity. Admins can pin/hide with an audit record. |
| Replenishment quantities | Human-in-the-loop | Forecast error can waste money or cause shortages. Dashboard shows intervals, risk, drift and held-out error. No automatic supplier order endpoint exists. |
| Customer segments | Human interpretation | Aggregate RFM clusters support analysis. Gift/deal labels are descriptive heuristics, not verified motives, individual eligibility or discriminatory decisions. |
| Price response | Research only | Simulated promotions confound observational coefficients. No automatic pricing, willingness-to-pay inference or causal claim. |
| Neural recommenders | Optional experiment | Opt-in routes, diagnostic learning curves and explicit evaluation limitations. Default serving remains the documented hybrid. |

Personalization requires an affirmative toggle and defaults off. Consent withdrawal removes events, recommendation references and quiz profile; future training excludes the user’s records. Functional wishlist/cart/orders remain to provide shopping features. Already learned aggregate model contributions are not instantly unlearned; scheduled retraining refreshes those aggregates. This tradeoff is explained in the product and the model cards.

Email and Argon2 password hashes stay in the account table. ML receives pseudonymous user IDs for aggregation, not emails, passwords, names, addresses or card details. Pseudonymous activity may still be personal data; access restrictions, session ownership and retention apply. The daily worker expires tracking/reference data after 180 days. Personal export is session-owned; admin CSV avoids emails and protects spreadsheet formula cells.

| Risk | Mitigation | Remaining limitation |
| --- | --- | --- |
| Consent bypass | Server gates tracking/training; CSRF/Origin checks; opt-out tests | Existing aggregate models need retraining for removal |
| Popularity/brand concentration | Content cold start, MMR brand penalty, coverage/diversity metrics | No demographic fairness claim; synthetic users have no demographic features |
| Overconfident matches | Shared-note explanations and cosine alignment label | Preferences and fragrance performance are subjective |
| Forecast error | Rolling origins, holdout scores, intervals, Croston, human review | 24 synthetic months cannot represent real shocks; 12-week bands extrapolate calibration |
| Unauthorized dashboard | Python role checks, opaque sessions, HttpOnly cookies, Argon2, session rotation | Internet production needs ingress rate limits, managed secrets, backups and incident procedures |
| Misleading evaluation | Simulated labels throughout; popularity baseline; actual JSON results | Generator choices can favour algorithms; no real uplift evidence |
| Model artifact tampering | Trusted local artifacts, checksum/path validation, atomic activation | Pickle is unsafe for untrusted inputs; disk access must be restricted |

An administrator owns deployment, data/holiday updates, artifact permissions and incident handling. Review drift/error alerts, stock recommendations and consent-removal refreshes. Product controls and stock edits write audit logs. Reassess the design before using real customers, consequential decisions or payment processing.
