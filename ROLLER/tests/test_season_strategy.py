"""2026-27 season selector. Official strategy is FIRST78→67. Live execution stays off."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

BOOK = REPO / "research/choosin_texas/library/nba_2q_regular_8040_1lot_2026_27/book.json"
FIRST80 = REPO / "ROLLER/roller/research/first80.py"
BOOK_HASH = "4da5fdd3a48d2a5513ab6e9452657a790514fbef389a05d0385cfaba009b8cf6"
FIRST80_HASH = "ba895f677938b8e1a33c2eb5d5a9835e8312a007ad207bcfee25f3f32eecb44f"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_official_season_selector_is_first78_67():
    from roller.momento.season_strategy import resolve_season_strategy

    body = resolve_season_strategy()
    assert body["official_strategy_id"] == "FIRST78_67"
    assert body["official_display_name"] == "FIRST78→67"
    assert body["live_execution"] is False
    assert body["submits"] is False
    assert body["validation_status"] == "NOT_YET_IDENTIFIABLE"
    assert body["labels"]["official"] == "Official upcoming-season strategy: FIRST78→67"
    assert body["labels"]["live_execution"] == "Live execution: disabled"
    assert body["labels"]["validation"] == "Validation: NOT_YET_IDENTIFIABLE"
    assert body["historical_research_book"]["book_id"] == "nba_2q_regular_8040_1lot_2026_27"
    assert body["historical_research_book"]["entry_cents"] == 80
    assert body["historical_research_book"]["stop_cents"] == 40
    assert body["historical_research_book"]["registration_status"] == "RESEARCH_REGISTERED"
    assert body["unresolved_execution"]["order_type"] == "UNRESOLVED"
    assert body["unresolved_execution"]["fee_applicability"] == "FEE_APPLICABILITY_UNVERIFIED"
    assert any("NOT_YET_IDENTIFIABLE" in line for line in body["validation_limitations"])
    assert _sha256(BOOK) == BOOK_HASH
    assert _sha256(FIRST80) == FIRST80_HASH


def test_season_strategy_http_and_displays():
    import terminal_api

    body = TestClient(terminal_api.app).get("/momento/season-strategy").json()
    assert body["official_strategy_id"] == "FIRST78_67"
    assert body["live_execution"] is False
    official = body["labels"]["official"]
    live = body["labels"]["live_execution"]
    validation = body["labels"]["validation"]
    momento = (REPO / "frontend/momento-systems/src/SeasonBanner.tsx").read_text()
    book = (REPO / "frontend/choosin-texas/src/Book.tsx").read_text()
    for label in (official, live, validation):
        assert label in momento
        assert label in book
    assert "HISTORICAL_REGISTERED_RESEARCH_BASELINE" in book
    assert "LEGACY_FIRST80_CONDITIONED_936" in momento
