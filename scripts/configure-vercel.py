"""Check the same-origin Vercel Services configuration without rewriting routes."""

import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
configuration = json.loads((root / "vercel.json").read_text())
services = configuration["services"]
assert services["api"]["framework"] == "fastapi"
assert services["storefront"]["framework"] == "vite"
assert configuration["rewrites"][0]["source"] == "/api/:path*"
assert configuration["rewrites"][0]["destination"]["service"] == "api"
print("Vercel Services routes checked. Import the repository root and configure")
print("DATABASE_URL, ENVIRONMENT, SECRET_KEY, ADMIN_PASSWORD and CRON_SECRET.")
print("The storefront uses /api on its own origin; no external API rewrite is needed.")
