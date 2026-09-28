"""Jump research filesystem. Pointers only. No silent merges."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

from roller.choosin_texas.locks_asked_six import ASKED_SIX_CELLS_80, ASKED_SIX_N_80
from roller.jump.drive import (
    handle_document,
    handle_preview,
    handle_refresh,
    handle_research,
    handle_research_children,
    handle_research_object,
    handle_root,
    handle_search,
    handle_sports,
    reset_library_cache,
)
from roller.jump.research import ASKED_SIX_DISPLAY, ASKED_SIX_KEY, resolve_jump_research_object

REPO = Path(__file__).resolve().parents[2]
JUMP_UI = REPO / "frontend" / "roller-terminal" / "src" / "jump"


def _client() -> TestClient:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import terminal_api

    return TestClient(terminal_api.app)


def setup_function() -> None:
    reset_library_cache()


def test_jump_default_sport_is_nba():
    root = handle_root()
    assert root["default_sport"] == "NBA"
    assert root["sport"] == "NBA"
    assert root["bot_ui"] is False
    assert root["live_execution"] is False
    assert root["writable"] is False
    names = [row["name"] for row in root["roots"]]
    assert names == ["NBA", "NCAAB", "MLB", "WNBA", "TENNIS"]
    keys = [row["canonical_key"] for row in root["children"]]
    assert ASKED_SIX_KEY in keys


def test_sport_switch_lists_and_empty_mlb():
    sports = handle_sports()["sports"]
    assert [row["id"] for row in sports] == ["NBA", "NCAAB", "MLB", "WNBA", "TENNIS"]
    ncaab = handle_research("NCAAB")
    assert [row["canonical_key"] for row in ncaab["objects"]] == [ASKED_SIX_KEY]
    wnba = handle_research("WNBA")
    assert [row["canonical_key"] for row in wnba["objects"]] == [ASKED_SIX_KEY]
    mlb = handle_research("MLB")
    assert mlb["count"] == 0
    assert mlb["empty_message"] == "No MLB research objects found."


def test_asked_six_is_one_folder_with_roller_and_superasi():
    asked = resolve_jump_research_object("asked_six")
    assert not isinstance(asked, list)
    assert asked.canonical_key == ASKED_SIX_KEY
    assert asked.display_name == ASKED_SIX_DISPLAY
    assert asked.population_n == 1182
    assert "NBA-only" not in asked.population_label or "not NBA-only" in asked.population_label
    assert asked.package_folder == "asked_six_first80_80_40"
    owners = {src.owner for src in asked.sources}
    assert "roller" in owners
    assert "superasi" in owners
    assert "choosin" in owners
    assert ASKED_SIX_N_80 == 1182
    assert tuple(ASKED_SIX_CELLS_80) == (883, 108, 0, 191)
    children = handle_research_children(ASKED_SIX_KEY)
    names = [row["name"] for row in children["children"]]
    assert "Overview" in names
    assert "ROLLER Measurement" in names
    assert "SuperASI Analysis" in names
    assert "Data" in names
    assert "Source Artifacts" in names


def test_vfgifapk_is_not_a_second_canonical_folder():
    objects = resolve_jump_research_object()
    assert isinstance(objects, list)
    keys = [obj.canonical_key for obj in objects]
    assert keys.count(ASKED_SIX_KEY) == 1
    assert "superasi_vfgifapk" not in keys
    asked = resolve_jump_research_object("superasi_vfgifapk")
    assert not isinstance(asked, list)
    assert asked.canonical_key == ASKED_SIX_KEY
    alias_paths = [row.path for row in asked.unresolved_aliases]
    assert any(path.endswith("superasi_vfgifapk") for path in alias_paths)
    nba_names = [
        row["canonical_key"] for row in handle_root("NBA")["children"] if row["canonical_key"] == ASKED_SIX_KEY
    ]
    assert nba_names == [ASKED_SIX_KEY]


def test_uuid_packages_are_not_merged_into_asked_six():
    objects = resolve_jump_research_object()
    assert isinstance(objects, list)
    uuids = [obj for obj in objects if obj.uuid]
    assert len(uuids) == 3
    for obj in uuids:
        assert obj.canonical_key != ASKED_SIX_KEY
        assert obj.display_name == "Untitled research object"
        assert obj.uuid == obj.canonical_key
        public = obj.as_dict()
        assert public["display_name"] != public["uuid"]
        assert public["metadata"]["uuid"] == obj.uuid


def test_documents_are_sourced_and_unavailable_when_missing():
    asked = handle_research_object(ASKED_SIX_KEY)["object"]
    docs = {row["slug"]: row for row in asked["documents"]}
    overview = docs["overview"]["body_markdown"]
    assert "1182" in overview
    results = docs["results"]["body_markdown"]
    assert "883" in results
    assert "Jump does not recompute EV" in results
    lineage = docs["lineage"]["body_markdown"]
    assert "asked_six_first80_80_40" in lineage
    assert "superasi_vfgifapk" in lineage
    untitled = [obj for obj in resolve_jump_research_object() if obj.uuid][0]
    definition = next(doc for doc in untitled.documents if doc.slug == "research-definition")
    assert "Unavailable" in definition.body_markdown


def test_provenance_survives_document_get():
    doc = handle_document(f"doc.{ASKED_SIX_KEY}.lineage")
    assert doc["writable"] is False
    assert doc["document"]["title"] == "Lineage"
    owners = {row["owner"] for row in doc["document"]["provenance"]}
    assert "roller" in owners
    assert "superasi" in owners
    assert doc["object"]["canonical_key"] == ASKED_SIX_KEY


def test_search_sort_and_folder_context():
    hits = handle_search("Asked Six")
    assert hits["count"] >= 1
    assert all(row["title"] != "superasi_vfgifapk" for row in hits["results"])
    assert any(row["title"] == ASKED_SIX_DISPLAY for row in hits["results"])
    uuid_hits = handle_search("58b3932deb124b96907273cc4fecc596")
    assert uuid_hits["count"] >= 1
    assert uuid_hits["results"][0]["title"] == "Untitled research object"
    assert uuid_hits["results"][0]["folder"] == "Untitled research object"


def test_preview_is_pointer_not_a_copy():
    preview = handle_preview(f"file.{ASKED_SIX_KEY}.package")
    assert preview["source_path"] == "research/superasi/library/asked_six_first80_80_40/package.json"
    assert "does not duplicate" in preview["note"]
    assert preview["preview"]["package_id"] == "asked_six_first80_80_40"


def test_refresh_rebuilds_readonly_sources():
    body = handle_refresh()
    assert body["status"] == "ok"
    assert body["writable"] is False
    assert body["object_count"] == 4
    asked = handle_research_object(ASKED_SIX_KEY)["object"]
    assert asked["writable"] is False


def test_research_http_routes():
    client = _client()
    root = client.get("/jump").json()
    assert root["sport"] == "NBA"
    assert client.get("/jump/sports").status_code == 200
    asked = client.get(f"/jump/research/{ASKED_SIX_KEY}").json()
    assert asked["object"]["display_name"] == ASKED_SIX_DISPLAY
    children = client.get(f"/jump/research/{ASKED_SIX_KEY}/children")
    assert children.status_code == 200
    doc = client.get(f"/jump/documents/doc.{ASKED_SIX_KEY}.overview")
    assert doc.status_code == 200
    refresh = client.post("/jump/index/refresh")
    assert refresh.status_code == 200
    ncaab = client.get("/jump/folders/sport.ncaab").json()
    child_keys = [row["canonical_key"] for row in ncaab["children"]]
    assert child_keys == [ASKED_SIX_KEY]
    assert ncaab["children"][0]["status"] == "SHARED"
    assert client.get("/jump/bots").status_code == 200


def test_jump_frontend_has_no_emoji_or_header_open_actions():
    sources = "\n".join(path.read_text(encoding="utf-8") for path in JUMP_UI.rglob("*.tsx"))
    sources += "\n" + "\n".join(path.read_text(encoding="utf-8") for path in JUMP_UI.rglob("*.ts"))
    assert "📁" not in sources
    assert "📄" not in sources
    top = (JUMP_UI / "JumpTopBar.tsx").read_text(encoding="utf-8")
    assert "Open ROLLER" not in top
    assert "Open SuperASI" not in top
    assert "Create Bot" not in sources
    assert "5180" not in sources
    assert "/jump/research" in sources
    shell = (JUMP_UI / "JumpShell.tsx").read_text(encoding="utf-8")
    assert "jumpHash" in shell
