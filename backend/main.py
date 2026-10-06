"""Vercel service entrypoint. Services preserve the original /api request path."""

import sys
from pathlib import Path
from fastapi import FastAPI

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from app.main import app as api, lifespan

app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/api", api)
