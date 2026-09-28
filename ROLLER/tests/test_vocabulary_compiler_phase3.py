"""Phase 3: deterministic vocabulary compiler."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from roller.dashboard_adapter.vocabulary_compiler import (
    COMPILER_VERSION,
    VOCABULARY_PATH,
    compile_research_text,
    load_vocabulary,
)


def test_vocabulary_loads_from_phase0_artifact():
    vocab = load_vocabulary()
    assert vocab["registry_version"] == "vocab_v0"
    assert VOCABULARY_PATH.exists()
    concepts = {c["concept"] for c in vocab["concepts"]}
    assert "FIRST_PRICE_TOUCH" in concepts
    assert "BIG_MOVE" in concepts


def test_exact_known_concept_no_invented_fields():
    result = compile_research_text("kalshi yes")
    ids = {m["concept_id"] for m in result["matches"]}
    assert "TERMINAL_YES" in ids
    assert result["proposed_spec"]["terminal_conditions"][0]["kind"] == "KALSHI_YES"
    # Must not invent FIRST80 path machinery
    assert result["proposed_spec"]["path_conditions"] == []
    assert result["compiler_version"] == COMPILER_VERSION


def test_first_price_touch_explicit_price():
    result = compile_research_text("first price touch 80")
    ids = {m["concept_id"] for m in result["matches"]}
    assert "FIRST_PRICE_TOUCH" in ids
    anchor = result["proposed_spec"]["anchor"]
    assert anchor["event"] == "FIRST_PRICE_TOUCH"
    assert anchor["price_e4"] == 8000
    # vocabulary defaults allowed
    assert anchor.get("price_field") == "yes_bid_close"
    assert anchor.get("requires_seen_below") is True


def test_first_time_hits_80_in_q3_vertical_slice():
    result = compile_research_text("first time price hits 80 in Q3")
    ids = {m["concept_id"] for m in result["matches"]}
    assert "FIRST_PRICE_TOUCH" in ids
    assert "PERIOD_Q3" in ids
    assert result["proposed_spec"]["anchor"]["event"] == "FIRST_PRICE_TOUCH"
    assert result["proposed_spec"]["anchor"]["event"] != "OBSERVATION_TIME"
    assert result["proposed_spec"]["anchor"]["price_e4"] == 8000
    assert "Q3" in result["proposed_spec"]["population_binding"]["default_structural_slices"]
    assert result["template_hint"] == "FIRST80_Q3"
    assert result["status"] == "RESOLVED"
    assert "first" not in result["unknown_terms"]
    assert result["unknown_terms"] == []
    # No silent template load of T40 / measurements
    assert result["proposed_spec"]["path_conditions"] == []
    applied = {b["concept"] for b in result["applied_bindings"]}
    assert "FIRST_PRICE_TOUCH" in applied
    assert "PERIOD_Q3" in applied


def test_when_price_first_reaches_75():
    result = compile_research_text("when price first reaches 75")
    ids = {m["concept_id"] for m in result["matches"]}
    assert "FIRST_PRICE_TOUCH" in ids
    assert result["proposed_spec"]["anchor"]["event"] == "FIRST_PRICE_TOUCH"
    assert result["proposed_spec"]["anchor"]["price_e4"] == 7500
    assert result["status"] == "RESOLVED"


def test_first_quarter_does_not_imply_first_price_touch():
    result = compile_research_text("first quarter Q3 price 80")
    ids = {m["concept_id"] for m in result["matches"]}
    assert "FIRST_PRICE_TOUCH" not in ids
    assert result["proposed_spec"]["anchor"]["event"] != "FIRST_PRICE_TOUCH"


def test_price_80_in_q3_does_not_create_first_price_touch():
    result = compile_research_text("price 80 in Q3")
    ids = {m["concept_id"] for m in result["matches"]}
    assert "FIRST_PRICE_TOUCH" not in ids
    assert result["proposed_spec"]["anchor"]["event"] != "FIRST_PRICE_TOUCH"
    # PERIOD may bind, but blank OBSERVATION_TIME is not a FIRST_PRICE_TOUCH claim
    assert "PERIOD_Q3" in ids or "Q3" in str(result["proposed_spec"]["population_binding"])


def test_status_not_resolved_from_blank_defaults_alone():
    """Recognized concept with missing required binding must not be RESOLVED via blank_spec."""
    result = compile_research_text("first time price hits")
    ids = {m["concept_id"] for m in result["matches"]}
    assert "FIRST_PRICE_TOUCH" in ids
    assert result["proposed_spec"]["anchor"]["event"] == "FIRST_PRICE_TOUCH"
    assert result["proposed_spec"]["anchor"].get("price_e4") is None
    assert result["status"] != "RESOLVED"
    assert any(u["field"] == "anchor.price_e4" for u in result["unresolved"])


def test_api_smoke_interpret_primary_dashboard_failure():
    pytest.importorskip("fastapi")
    import sys

    from fastapi.testclient import TestClient

    scripts = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(scripts))
    import terminal_api  # noqa: E402

    client = TestClient(terminal_api.app)
    r = client.post(
        "/query/interpret",
        json={"text": "first time price hits 80 in Q3"},
    )
    assert r.status_code == 200
    body = r.json()
    ids = {m["concept_id"] for m in body["matches"]}
    assert "FIRST_PRICE_TOUCH" in ids
    assert body["status"] == "RESOLVED"
    assert body["proposed_spec"]["anchor"]["event"] == "FIRST_PRICE_TOUCH"
    assert body["proposed_spec"]["anchor"]["price_e4"] == 8000
    assert "first" not in body["unknown_terms"]
    assert body["template_hint"] == "FIRST80_Q3"

def test_qualitative_magnitude_unresolved():
    result = compile_research_text("large downward move")
    assert result["status"] in ("PARTIAL", "UNRESOLVED")
    fields = {u["field"] for u in result["unresolved"]}
    assert "anchor.magnitude_e4" in fields
    mag = result["proposed_spec"]["anchor"].get("magnitude_e4")
    assert mag is None
    # Must not invent a number
    assert not any(
        isinstance(result["proposed_spec"]["anchor"].get(k), int)
        and k == "magnitude_e4"
        for k in ("magnitude_e4",)
    )
    reasons = " ".join(u["reason"] for u in result["unresolved"])
    assert "threshold" in reasons.lower() or "explicit" in reasons.lower()


def test_explicit_magnitude_down_15_cents():
    result = compile_research_text("down 15 cents")
    anchor = result["proposed_spec"]["anchor"]
    assert anchor["event"] == "PRICE_MOVE"
    assert anchor["direction"] == "DOWN"
    assert anchor["magnitude_e4"] == 1500
    assert not any(u["field"] == "anchor.magnitude_e4" for u in result["unresolved"])


def test_unknown_words_banana_signal():
    result = compile_research_text("banana signal")
    assert result["status"] == "NO_MATCH"
    assert "banana" in result["unknown_terms"] or "signal" in result["unknown_terms"]
    assert result["matches"] == []
    # blank shell only — no invented research bindings
    assert result["proposed_spec"]["anchor"]["event"] == "OBSERVATION_TIME"
    assert result["proposed_spec"]["measurement_requests"] == []


def test_compiler_does_not_import_execution_modules():
    src = Path(__file__).resolve().parents[1] / "roller" / "dashboard_adapter" / "vocabulary_compiler.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    forbidden = (
        "roller.research",
        "explorer",
        "object_inspector",
        "openai",
        "anthropic",
        "httpx",
        "requests",
    )
    joined = " ".join(imports)
    for bad in forbidden:
        assert bad not in joined, f"forbidden import {bad} in vocabulary_compiler"


def test_api_smoke_interpret_and_vocabulary():
    pytest.importorskip("fastapi")
    import sys

    from fastapi.testclient import TestClient

    scripts = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(scripts))
    import terminal_api  # noqa: E402

    client = TestClient(terminal_api.app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["phase"] >= 3
    assert "vocabulary_compiler" in health.json()["capabilities"]

    vocab = client.get("/vocabulary")
    assert vocab.status_code == 200
    assert vocab.json()["registry_version"] == "vocab_v0"

    r = client.post(
        "/query/interpret",
        json={"text": "first time price hits 80 in Q3"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["proposed_spec"]["anchor"]["event"] == "FIRST_PRICE_TOUCH"
    assert body["proposed_spec"]["anchor"]["price_e4"] == 8000
    assert body["template_hint"] == "FIRST80_Q3"
    assert "FIRST_PRICE_TOUCH" in {m["concept_id"] for m in body["matches"]}

    # language alias still accepted
    r2 = client.post("/query/interpret", json={"language": "banana signal"})
    assert r2.status_code == 200
    assert r2.json()["status"] == "NO_MATCH"

    # qualitative not fabricated
    r3 = client.post("/query/interpret", json={"text": "big move"})
    assert r3.status_code == 200
    assert r3.json()["proposed_spec"]["anchor"].get("magnitude_e4") is None
