"""TK Ultra is Relative Value Hedging frontend. Not an 18th system."""

from __future__ import annotations

import sys
from fractions import Fraction
from pathlib import Path

from fastapi.testclient import TestClient

from roller.momento.registry import SYSTEM_COUNT, load_registry
from roller.momento.relative_value import evaluate
from roller.momento.tk_ultra import NQ_ES_EXAMPLE, source_letter_path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


def _client() -> TestClient:
    import terminal_api

    return TestClient(terminal_api.app)


def test_tk_ultra_is_not_an_18th_system():
    registry = load_registry()
    assert len(registry.systems) == SYSTEM_COUNT == 19
    assert "tk_ultra" not in registry.by_id()
    row = registry.by_id()["relative_value_hedging"]
    assert row.frontend_url == "http://127.0.0.1:5190/#/tk-ultra"
    assert row.frontend_product == "TK Ultra"
    assert row.extra.get("visual_subtitle") == "TK Ultra"
    assert row.api_namespace == "/momento/tk-ultra"


def test_nq_es_letter_example_matches_published_ticks():
    result = evaluate(
        wing_price=Fraction(NQ_ES_EXAMPLE["wing_price"]),
        base_price=Fraction(NQ_ES_EXAMPLE["base_price"]),
        beta=Fraction(NQ_ES_EXAMPLE["beta"]),
        wing_anchor=Fraction(NQ_ES_EXAMPLE["wing_anchor"]),
        base_anchor=Fraction(NQ_ES_EXAMPLE["base_anchor"]),
        ticks_per_handle=int(NQ_ES_EXAMPLE["ticks_per_handle"]),
    )
    payload = result.payload()
    assert payload["reading"] == "WING_CHEAP"
    assert payload["rv_ticks"] == "-247.92"
    assert payload["relationship_multiplier"] == "4.2427"
    assert payload["binary_formula_is_truth"] is False
    letter = NQ_ES_EXAMPLE["published"]
    assert letter["rv_ticks"] == "-247.92"


def test_tk_ultra_desk_and_assess():
    client = _client()
    desk = client.get("/momento/tk-ultra").json()
    assert desk["live_execution"] is False
    assert desk["system_id"] == "relative_value_hedging"
    assert desk["title"] == "TK Ultra"
    assert desk["binary_formula_is_truth"] is False
    letter = desk["source_letter"]
    assert letter["from_email"] == "louiexfinance@gmail.com"
    assert "14033" in letter["body"]
    assert "-247.92" in letter["body"]
    assert source_letter_path().is_file()
    assert desk["worked_example"]["engine"]["rv_ticks"] == "-247.92"
    assert desk["corridor"]["windows"][1]["cents"] == 45
    assert desk["corridor"]["windows"][2]["cents"] == 35
    missing = client.get("/momento/tk-ultra/assess").json()
    assert missing["status"] == "SOURCE_UNAVAILABLE"
    assert "wing_price" in missing["missing"]
    nq = client.get(
        "/momento/tk-ultra/assess",
        params={
            "wing_price": "14033",
            "base_price": "4382.50",
            "beta": "1.325",
            "wing_anchor": "13954.8",
            "base_anchor": "4349.46",
            "ticks_per_handle": "4",
        },
    ).json()
    assert nq["status"] == "RESEARCH_ONLY"
    assert nq["reading"] == "WING_CHEAP"
    assert nq["rv_ticks"] == "-247.92"
    bad = client.get(
        "/momento/tk-ultra/assess",
        params={
            "wing_price": "1",
            "base_price": "0",
            "beta": "1",
            "wing_anchor": "1",
            "base_anchor": "1",
            "ticks_per_handle": "1",
        },
    )
    assert bad.status_code == 400
    assert bad.json()["detail"]["code"] == "INVALID_INPUT"


def test_frontend_routes_tk_ultra():
    frontend = Path(__file__).resolve().parents[2] / "frontend" / "momento-systems" / "src"
    app = (frontend / "App.tsx").read_text(encoding="utf-8")
    desk = (frontend / "TkUltra.tsx").read_text(encoding="utf-8")
    api = (frontend / "api.ts").read_text(encoding="utf-8")
    assert "/tk-ultra" in app
    assert "SOURCE_UNAVAILABLE" in desk
    assert "/api/momento/tk-ultra" in api
    assert "5180" not in desk
