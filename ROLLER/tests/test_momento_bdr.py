"""BDR catalog is Hedging Analysis write-up library. Not live. Not the product Frontend."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

from roller.momento.registry import SYSTEM_COUNT, load_registry

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


def _client() -> TestClient:
    import terminal_api

    return TestClient(terminal_api.app)


def test_bdr_is_not_an_18th_system():
    registry = load_registry()
    assert len(registry.systems) == SYSTEM_COUNT == 19
    assert "bdr" not in registry.by_id()
    assert registry.by_id()["hedging_analysis"].frontend_url == "http://127.0.0.1:5192/"
    assert registry.by_id()["hedging_analysis"].frontend_product == "Ballhog"
    assert "research/bdr/" in registry.by_id()["hedging_analysis"].research_paths


def test_bdr_catalog_and_documents():
    client = _client()
    catalog = client.get("/momento/bdr").json()
    assert catalog["live_execution"] is False
    assert catalog["system_id"] == "hedging_analysis"
    assert catalog["title"] == "BDR # MOMENTO SYSTEMS"
    slugs = [row["slug"] for row in catalog["documents"]]
    assert slugs == [
        "program",
        "dual-leg-lock",
        "liquidation-corridor",
        "acquisition-corridor",
        "asked-six-liquidation",
        "loss-review-2026-08-25",
        "a1-hybrid-hedge",
        "77-ridge",
        "staged-acquisition",
    ]
    assert catalog["subtitle"].startswith("Staged acquisition")
    for slug in slugs:
        body = client.get(f"/momento/bdr/{slug}").json()
        assert body["live_execution"] is False
        assert body["slug"] == slug
        assert body["markdown"]
    thesis = client.get("/momento/bdr/acquisition-corridor").json()
    assert "NOT_RUN" in thesis["markdown"]
    assert "LIVE EXECUTION" in thesis["markdown"]
    assert "0.5732" in thesis["markdown"]
    ridge = client.get("/momento/bdr/77-ridge").json()
    md = ridge["markdown"]
    assert ridge["live_execution"] is False
    assert "NOT_RUN" in md
    assert "LIVE EXECUTION" in md
    assert "5.1222" in md
    assert "933 ≠ 936" in md
    assert "NOT_ARMED" in md
    assert "CANDLE PATH" in md
    assert "+5.1222" in md
    for invented in ("74/40 +", "76/40 +", "78/40 +", "79/40 +", "77/27 +", "80/53 +"):
        assert invented not in md
    staged = client.get("/momento/bdr/staged-acquisition").json()
    sm = staged["markdown"]
    assert staged["live_execution"] is False
    assert "NOT_RUN" in sm
    assert "LIVE EXECUTION" in sm
    assert "0.0188" in sm
    assert "0.4821" in sm
    assert "COMMON-INTERSECTION" in sm
    assert "5.1222" in sm
    assert "5.1410" in sm
    assert "5.6043" in sm
    assert "913" in sm and "973" in sm
    missing = client.get("/momento/bdr/not-a-doc")
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "UNKNOWN_DOCUMENT"
