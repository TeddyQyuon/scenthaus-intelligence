# Quick add and account security verification

2026-10-07 follow-up to the existing 150-product reference catalogue.

Implemented quick-add size/quantity selection with exact totals, additive bag writes serialized by user, quantity-based bag counts, authenticator QR/manual setup, enforced second-factor sign-in, single-use recovery codes, password changes, active sessions with timestamps/IP/approximate location, remote session revocation and successful/failed login/security history. Security records are included in the personal data export and retained for 90 days independently of personalization consent.

Local verification used native PostgreSQL 18.4, the actual seeded reference catalogue, Python 3.12 and Chromium:

- All 84 Python tests passed after full native model training. These include 15 account-security/cart integration tests for concurrent recovery-code consumption and bag additions, session ownership/revocation, missing/invalid second factors, recovery-code regeneration, password rotation, server-backed rate limits, untrusted metadata rejection, secret-free exports and an upgrade of pre-security sessions. Existing checkout, consent, admin, model-integrity, training, inference and build-lock checks also passed.
- All six browser journeys passed, including the two new journeys for mobile variant/quantity selection, bag reload, listing position/focus, Escape dismissal, account creation, authenticator setup, recovery sign-in, password change and mobile account layout. Existing catalogue, search, wishlist, consent, demo checkout and admin/forecast flows passed.
- Ruff, whitespace checks and the frontend production build passed.
- An isolated environment containing only the declared Vercel runtime dependencies and the HTTP test transport passed API startup, catalogue counts, JWT authentication, ONNX search, protected forecasts and authorized bulk maintenance. PyTorch, Sentence Transformers, MLflow and LightGBM were absent.

The complete browser run exposed two timing/rate-limit issues. The existing product-detail journey now waits for the bag confirmation before navigating. Account/security GET requests use the ordinary read budget; credential/security writes retain the 30-per-minute IP limit and the persistent failed-verification limits. Two new PostgreSQL tests verify that account reads do not consume the sign-in budget and that authentication writes remain limited. The corrected full browser run passed without skips or flaky results.

Hosted deployment checks remain required before the public alias is updated. Older sessions keep working after migration; their missing historical login metadata is displayed as not recorded. Generated local datasets, trained weights and evaluation output were kept outside the committed source.

Publishing was attempted through both Git and the connected GitHub branch tool. Both were rejected with HTTP 403; the native error was `Resource not accessible by integration`. The available cloud-browser profile was signed out of GitHub and Vercel. Source is committed locally on `feat/quick-add-account-security`.

Direct Vercel source uploads succeeded for all 310 tracked files. Initial Preview `dpl_2b6VgEsjjtbKeevU7DmjWMUEr6VT` and queued Production `dpl_2YXYX5QGmqdXX7HJSuGYEEoPMgKt` were canceled after the browser rate-limit regression was found. The corrected source is ready for a staged Production build and hosted verification. Automatic production-domain assignment remains disabled until verification; no new live-release claim is made here.
