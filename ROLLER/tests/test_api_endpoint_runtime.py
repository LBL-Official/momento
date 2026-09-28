"""API ownership / endpoint routing. Does not change research semantics or FIRST80."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

ROLLER_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_SRC = ROLLER_ROOT.parent / "frontend" / "roller-terminal" / "src"
VITE_CONFIG = ROLLER_ROOT.parent / "frontend" / "roller-terminal" / "vite.config.ts"

ASKED_SIX_DRAFT = {
    "universe": {
        "sports": ["Basketball"],
        "leagues": ["NBA", "NCAAB"],
        "seasons": ["2025-2026"],
        "dateFrom": "2025-10-10",
        "dateTo": "2026-06-13",
        "markets": ["kalshi"],
        "marketData": ["candles"],
        "dataSources": [],
    },
    "entryConditions": [
        {
            "id": "e1",
            "family": "first_touch",
            "priceCents": 80,
            "touchN": 1,
            "periodWindows": [
                {"period": "Q2"},
                {"period": "Q3"},
                {"period": "H1_2"},
                {"period": "H2_1"},
            ],
        }
    ],
    "exitConditions": [
        {
            "id": "p-loss",
            "kind": "path",
            "family": "reach",
            "priceCents": 35,
            "outcome": "loss",
        },
        {
            "id": "h-win",
            "kind": "terminal",
            "family": "hold_expiration_win",
            "outcome": "win",
        },
    ],
    "teFilters": {"scoreSide": "leading", "absDiff": "6_10"},
    "recognizedIntent": {"status": "EMPTY"},
    "status": "DRAFT",
}


def _client() -> TestClient:
    import sys

    sys.path.insert(0, str(ROLLER_ROOT / "scripts"))
    import terminal_api

    return TestClient(terminal_api.app)


def test_health_is_reachable_shape():
    body = _client().get("/health").json()
    assert body["status"] == "ok"
    assert "research_query_compile" in body["capabilities"]
    assert "research_query_execute" in body["capabilities"]
    assert "research_query_jobs" in body["capabilities"]
    assert "research_library_saves" in body["capabilities"]
    assert body["reachable_during_execute"] is True
    assert "research_query_official_settlement" in body["capabilities"]
    assert body["settlement"]["terminal_source"] == "official_first80_expiration_result_yes"
    assert body["settlement"]["status"] in {"AVAILABLE", "ABSENT"}


def test_compile_ignores_client_execution_path():
    from roller.research_query.hashing import layer_hashes
    from roller.research_query.compiler import compile_draft

    client = _client()
    honest = client.post("/research-query/compile", json={"draft": ASKED_SIX_DRAFT})
    steered = client.post(
        "/research-query/compile",
        json={
            "draft": ASKED_SIX_DRAFT,
            "execution_path": "frozen_reference",
            "reference_match": "FIRST80_Q3",
            "status": "READY",
        },
    )
    assert honest.status_code == 200
    assert steered.status_code == 200
    a, b = honest.json(), steered.json()
    assert a["execution_path"] == b["execution_path"] == "generic_query"
    assert a["reference_match"] is None
    assert a["hashes"]["question_hash"] == b["hashes"]["question_hash"]
    compiled = compile_draft(ASKED_SIX_DRAFT)
    local = layer_hashes(compiled.question, state=ASKED_SIX_DRAFT["teFilters"])
    assert a["hashes"]["question_hash"] == local["question_hash"]


def test_frontend_has_no_api_lifecycle_and_uses_base():
    banned = ("pkill", "killExisting", "spawnApi", "stopApi(", "lsof -ti")
    fetch_rel = 'fetch("/api/'
    hits_banned: list[str] = []
    leftover_fetch: list[str] = []
    for path in FRONTEND_SRC.rglob("*"):
        if path.suffix not in {".ts", ".tsx"}:
            continue
        if "node_modules" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for token in banned:
            if token in text:
                hits_banned.append(f"{path}: {token}")
        if fetch_rel in text:
            leftover_fetch.append(str(path))
    assert not hits_banned, hits_banned
    assert not leftover_fetch, leftover_fetch
    base = (FRONTEND_SRC / "api" / "base.ts").read_text(encoding="utf-8")
    assert "http://127.0.0.1:8791" in base
    assert "VITE_API_BASE_URL" in base
    vite = VITE_CONFIG.read_text(encoding="utf-8")
    assert "127.0.0.1:8791" in vite


def test_ensure_script_never_kills():
    text = (ROLLER_ROOT / "scripts" / "ensure_terminal_api.py").read_text(encoding="utf-8")
    for token in ("pkill", "kill ", "lsof -ti", "terminate"):
        assert token not in text
    assert "API_REACHABLE" in text
    assert "Not killed" in text


def test_resolve_api_base_precedence_documented():
    text = (FRONTEND_SRC / "api" / "base.ts").read_text(encoding="utf-8")
    assert "env.DEV === false) return \"/api\"" in text or 'return "/api"' in text
    assert "DEV_API_ORIGIN" in text


def test_results_page_keeps_terminal_path():
    answer = (FRONTEND_SRC / "v2" / "results" / "ResultsAnswer.tsx").read_text(encoding="utf-8")
    tree = (FRONTEND_SRC / "v2" / "results" / "EmpiricalTree.tsx").read_text(encoding="utf-8")
    assert "Settlement missing" not in answer
    assert "UNAVAILABLE — selecting hold does not create settlement" not in answer
    assert "Hold-to-YES path" in answer or "hold path" in answer
    assert "Missing settlement" not in tree
    assert "Hold-to-YES path" in tree


def test_api_unreachable_is_not_empty_research_result():
    status = (FRONTEND_SRC / "v2" / "researchStatus.ts").read_text(encoding="utf-8")
    app = (FRONTEND_SRC / "App.tsx").read_text(encoding="utf-8")
    assert 'title: "API_UNREACHABLE"' in status
    assert "Not an empty population" in status
    assert 'title: "API_REQUEST_FAILED"' in status
    assert "This is not N = 0, DATA REQUIRED, or an empty population" in app
    rq = (FRONTEND_SRC / "api" / "researchQuery.ts").read_text(encoding="utf-8")
    assert "executeResearchQuery" in rq
    assert "pollResearchJob" in rq
    assert "saveResultToServer" in rq
    assert "executeResearchQuery" in app
