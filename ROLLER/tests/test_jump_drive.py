"""Jump Drive. Sport-first research library. No bot UI."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

from roller.jump.drive import handle_folder, handle_root, handle_search, reset_library_cache
from roller.jump.research import ASKED_SIX_KEY

REPO = Path(__file__).resolve().parents[2]
JUMP_UI = REPO / "frontend" / "roller-terminal" / "src" / "jump"


def _client() -> TestClient:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import terminal_api

    return TestClient(terminal_api.app)


def setup_function() -> None:
    reset_library_cache()


def test_drive_root_and_first80():
    root = handle_root()
    assert root["bot_ui"] is False
    assert root["live_execution"] is False
    names = [row["name"] for row in root["roots"]]
    assert names == ["NBA", "NCAAB", "MLB", "WNBA", "TENNIS"]
    first80 = handle_folder(f"research.{ASKED_SIX_KEY}")
    child_names = [row["name"] for row in first80["children"]]
    assert "ROLLER Measurement" in child_names
    assert "SuperASI Analysis" in child_names
    assert "Data Model" in child_names
    hits = handle_search("FIRST80")
    assert hits["count"] >= 1
    assert all("bot" not in row["name"].lower() for row in hits["results"])


def test_drive_http_and_bots_http_still_exists():
    client = _client()
    drive = client.get("/jump").json()
    assert drive["role"] == "data_modeling_drive"
    assert drive["sport"] == "NBA"
    assert client.get("/jump/tree").status_code == 200
    assert client.get("/jump/folders/sport.nba").status_code == 200
    assert client.get("/jump/search", params={"q": "NBA"}).status_code == 200
    health = client.get("/jump/health").json()
    assert health["bot_ui"] is False
    assert health["role"] == "data_modeling_drive"
    assert client.get("/jump/bots").status_code == 200


def test_bracket_visual_omits_ingest_to_database_wire():
    layout = REPO / "frontend" / "momento-systems" / "src" / "layout.ts"
    text = layout.read_text(encoding="utf-8").replace(" ", "")
    assert '["data_ingestion","database"]' not in text


def test_jump_frontend_has_no_bot_or_vital():
    sources = "\n".join(path.read_text(encoding="utf-8") for path in JUMP_UI.rglob("*.tsx"))
    sources += "\n" + "\n".join(path.read_text(encoding="utf-8") for path in JUMP_UI.rglob("*.ts"))
    assert "Create Bot" not in sources
    assert "My Bots" not in sources
    assert "Bot Creation" not in sources
    assert "openVitalDashboard" not in sources
    assert "/vital/" not in sources
    assert "5180" not in sources
    assert "/jump/tree" in sources or "/jump" in sources
    assert "📁" not in sources
    assert "📄" not in sources
