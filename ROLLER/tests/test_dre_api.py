"""DRE adapter. Choosin Texas + Austin only. No Vital / bots / crates/risk."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[2]
DRE_UI = REPO / "frontend" / "dynamic-risk-engine" / "src"
DRE_PY = Path(__file__).resolve().parents[1] / "roller" / "dre"


def _client() -> TestClient:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import terminal_api

    return TestClient(terminal_api.app)


def test_dre_health_flags():
    body = _client().get("/dre/health").json()
    assert body["product"] == "DRE"
    assert body["live_execution"] is False
    assert body["submits"] is False
    assert body["phase3_is_execution_policy"] is False
    assert body["live_feed"] == "UNAVAILABLE"
    assert "trade_breakdown" in body["upstream"]
    assert "position_stratification" in body["upstream"]
    objective = body["objective"]
    assert objective["id"] == "DRE_PORTFOLIO_OBJECTIVE_V1"
    assert objective["calculus"] == "NOT_IMPLEMENTED"
    assert objective["ssot"] == "research/dre/PORTFOLIO_OBJECTIVE_V1.md"
    assert objective["forward_feed"] == [
        "trade_breakdown",
        "position_stratification",
    ]


def test_dre_desk_and_upstream_wrap_choosin_and_austin():
    client = _client()
    desk = client.get("/dre").json()
    assert desk["product"] == "DRE"
    assert desk["live_execution"] is False
    assert desk["hold_reason_intact"] == "UNKNOWN"
    assert desk["objective"]["eventual_form"] == "ΔP → ΔP*(Xt)"
    assert desk["objective"]["calculus"] == "NOT_IMPLEMENTED"
    trade = desk["trade_breakdown"]
    if trade.get("status") == "OBSERVED":
        assert trade["n"] == 936
        assert trade["source"] == "choosin_texas"
    stratum = desk["stratum"]
    if stratum.get("status") == "OBSERVED":
        assert stratum["book_n"] == 604
        assert stratum["source"] == "austin"
        assert stratum["live_feed"] == "UNAVAILABLE"
    assert client.get("/dre/upstream/trade-breakdown").status_code == 200
    assert client.get("/dre/upstream/stratum").status_code == 200
    assert client.get("/dre/experiments").status_code == 200


def test_dre_python_only_imports_choosin_and_austin():
    tree = ast.parse((DRE_PY / "api.py").read_text(encoding="utf-8"))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
    banned = ("roller.vital", "roller.jump", "crates", "kalshi")
    for name in imported:
        assert not any(name.startswith(item) for item in banned), name
    assert any(name.startswith("roller.choosin_texas") for name in imported)
    assert any(name.startswith("roller.austin") for name in imported)


def test_dre_frontend_has_no_vital_or_bots():
    if not DRE_UI.is_dir():
        return
    sources = "\n".join(path.read_text(encoding="utf-8") for path in DRE_UI.rglob("*.tsx"))
    sources += "\n" + "\n".join(path.read_text(encoding="utf-8") for path in DRE_UI.rglob("*.ts"))
    assert "/api/dre" in sources
    assert "#/objective" in sources
    assert "PORTFOLIO_OBJECTIVE_V1" in sources
    assert "Choosin Texas" in sources
    assert "Austin" in sources
    assert "/vital" not in sources
    assert "/jump/bots" not in sources
    assert "5180" not in sources
    assert "Create Bot" not in sources


def test_dre_portfolio_objective_docs_exist():
    library = REPO / "research" / "dre"
    assert (library / "README.md").is_file()
    objective = (library / "PORTFOLIO_OBJECTIVE_V1.md").read_text(encoding="utf-8")
    greeks = (library / "GREEK_STACK_V1.md").read_text(encoding="utf-8")
    assert "ΔP → ΔP*(Xt)" in objective
    assert "Choosin Texas" in objective
    assert "Austin" in objective
    assert "NOT_IMPLEMENTED" in objective or "not implemented" in objective.lower()
    assert "Λα ≠ Δ ≠ Γ ≠ β" in greeks
    assert "Δ↓ ⇏ α↑" in greeks
    assert "Do not pretend we know how to calculate" in greeks
