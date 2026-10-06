# Privacy, human oversight and model limits

This is an engineering description for a portfolio demonstration, not legal advice, a PDPA compliance opinion or a certification. The real-product reference catalogue is paired with **SIMULATED** users, quiz profiles, browsing activity, orders, prices and stock.

## User control

- Personalization starts off. A user can opt in from the privacy settings.
- Without consent, `POST /events` declines tracking. A quiz answer is used for that response and is not saved as a profile.
- With consent, product interactions and quiz profiles may be used for personalization and future model training. Training joins each record to the account's current consent state and excludes users who have withdrawn.
- Withdrawal deletes the user's tracked events, quiz profile and recommendation references. Wishlist, cart and demo orders remain as functional account data. Previously trained aggregate model contributions update only after a later model build.
- The user can export account, quiz, wish-list, order and event records through the session-owned privacy export route.
- Events and recommendation references expire after the configured 180-day retention period; expired sessions are deleted by the daily maintenance route.

## Data handling

Email addresses and password hashes are account data and are not model features. Passwords are Argon2-hashed; opaque high-entropy session tokens are stored as digests in PostgreSQL and sent in HttpOnly cookies. Model features use a pseudonymous account identifier and preference/history signals. Pseudonymisation is not anonymisation.

Admin endpoints require an admin role. User-owned cart, wishlist, order and export routes enforce ownership. Event writes validate recommendation ownership and product membership before attribution. Admin exports avoid account email; formula-like spreadsheet values are neutralized.

## Human involvement

| Output | Human role | Control |
| --- | --- | --- |
| Fragrance recommendations and search | Shopper decides whether to inspect or buy | Consent, filters, explainable note/accord tags, eligibility checks and product hide/pin settings |
| Forecast and stock-risk signals | Admin reviews the forecast and inventory context | Model picker, historical validation metrics and interval bands; no automated purchase/order endpoint |
| Customer aggregates | Admin interprets summaries | Aggregated reporting; no eligibility or consequential decision |
| Pricing or willingness-to-pay | Not used for automatic decisions | Promotion correlations are not treated as causal evidence |

## Risks and limits

| Risk | Current mitigation | Remaining limitation |
| --- | --- | --- |
| Tracking without permission | Consent checks are enforced by API routes and covered by tests | Functional commerce records remain when tracking is withdrawn |
| Popularity or brand concentration | Brand-diversity metric, content fallback, eligibility filters and user-visible explanations | No demographic fairness claim; synthetic users contain no demographic features |
| Overstated quiz match | UI describes match as accord alignment, not a probability | Fragrance preferences and performance are subjective |
| Misleading search scores | Draft labels are explicitly marked unreviewed | No independent human relevance set |
| Forecast error | Baselines, chronological evaluation and measured interval coverage are shown | Simulated history is short; category coverage is poor in this run and 12-week accuracy is not established |
| Model/artifact misuse | Trusted build artifacts, versioning and checksum/path validation | Pickle files are unsafe if supplied by an untrusted source; restrict build and artifact access |

Before adding real customer data, payments, automated purchasing or supplier actions, review the legal basis, consent language, access controls, retention policy, incident handling, backups and model evaluation with the accountable owner. Forecasts and recommendation metrics must be recomputed on suitable real-world data before any operational claim.
