#!/usr/bin/env python3
"""Momento LS API. Direct observe of momento-live.service. Port 8792."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ROLLER"))

from roller.ls.api import handle_health, handle_observe, handle_snapshot

app = FastAPI(title="Momento LS", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5181",
        "http://localhost:5181",
    ],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return handle_health()


@app.get("/ls/health")
def ls_health() -> dict:
    return handle_health()


@app.get("/observe")
def observe() -> dict:
    return handle_observe()


@app.get("/ls/observe")
def ls_observe() -> dict:
    return handle_observe()


@app.get("/snapshot")
def snapshot() -> dict:
    return handle_snapshot()


if __name__ == "__main__":
    import uvicorn

    host = os.environ.get("MOMENTO_LS_API_HOST", "127.0.0.1")
    port = int(os.environ.get("MOMENTO_LS_API_PORT", "8792"))
    uvicorn.run(app, host=host, port=port)
