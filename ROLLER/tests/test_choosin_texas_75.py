"""Choosin Texas (75) FIRST75 four-partition locks. Integers are the authority."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from roller.choosin_texas.api import handle_health, handle_universe, handle_universe_75
from roller.choosin_texas.locks75 import (
    ASKED_SIX_CELLS_75,
    ASKED_SIX_N_75,
    BARRIER_55_75,
    BARRIER_55_POOL_CELLS_75,
    BARRIER_55_POOL_EXCL_75,
    BARRIER_55_POOL_N_75,
    MID_STOPS_75,
    PARTITIONS_75,
    PATH_STOPS_75,
    ladder_cells_75,
    POOL_CELLS_75,
    POOL_L_75,
    POOL_N_75,
    POOL_W_75,
    WNBA_UNION_CELLS_75,
    WNBA_UNION_N_75,
)
from roller.choosin_texas.models import ChoosinTexasError
from roller.choosin_texas.nba_path75 import build_nba_path_75
from roller.choosin_texas.texas75 import verify_locks_75


REPO = Path(__file__).resolve().parents[2]
FRONTEND_APP = REPO / "frontend" / "choosin-texas" / "src" / "App.tsx"
FRONTEND_TEXAS75 = REPO / "frontend" / "choosin-texas" / "src" / "Texas75.tsx"


def test_first75_lock_integers_match_tables_md():
    expected = {
        "nba_2q": (318, 242, 76, (208, 34, 1, 75)),
        "nba_3q": (258, 192, 66, (167, 25, 0, 66)),
        "ncaab_h1_2": (204, 152, 52, (126, 26, 0, 52)),
        "ncaab_h2_1": (133, 110, 23, (99, 11, 0, 23)),
    }
    for lock in PARTITIONS_75:
        assert (lock.n, lock.W, lock.L, lock.cells) == expected[lock.partition_id]
    assert sum(p.n for p in PARTITIONS_75) == POOL_N_75 == 913
    assert sum(p.W for p in PARTITIONS_75) == POOL_W_75 == 696
    assert sum(p.L for p in PARTITIONS_75) == POOL_L_75 == 217
    assert POOL_CELLS_75 == (600, 96, 1, 216)
    assert ASKED_SIX_N_75 == 1126
    assert WNBA_UNION_N_75 == 213
    assert POOL_N_75 + WNBA_UNION_N_75 == ASKED_SIX_N_75
    assert ASKED_SIX_CELLS_75 == (750, 121, 1, 254)
    assert WNBA_UNION_CELLS_75 == (150, 25, 0, 38)


def test_first75_s_includes_lose_no_and_is_not_first80():
    verified = verify_locks_75()
    assert verified["status"] == "OBSERVED"
    assert verified["pool"]["n"] == 913
    assert verified["pool"]["rule"] == "FIRST75"
    assert verified["pool"]["trade_75_40"]["S_display"] == "601/913"
    assert verified["pool"]["trade_75_40"]["key"] == "75/40"
    assert verified["pool"]["trade_75_40"]["gain_cents"] == 25
    assert verified["pool"]["trade_75_40"]["loss_cents"] == 35
    assert verified["pool"]["trade_75_40"]["book_cents"] == 4105
    assert verified["pool"]["trade_75_40"]["ev_display"] == "4105/913 ¢"
    assert verified["pool"]["trade_75_40"]["ev_per_trade_display"] == "+4.4962¢ / trade"
    assert "trade_80_40" not in verified["pool"]
    by_id = {row["partition_id"]: row for row in verified["partitions"]}
    assert by_id["nba_2q"]["s_L"]["numer"] == 1
    assert by_id["nba_2q"]["trade_75_40"]["S_display"] == "209/318"
    assert by_id["nba_2q"]["cells"]["L_and_not_T40"] == 1
    assert by_id["nba_3q"]["n"] == 258
    assert by_id["ncaab_h1_2"]["n"] == 204
    assert by_id["ncaab_h2_1"]["n"] == 133
    assert [row["key"] for row in verified["pool"]["paths"]] == [
        "75/25",
        "75/30",
        "75/35",
        "75/40",
        "75/45",
        "75/50",
        "75/55",
    ]
    assert verified["pool"]["paths"][2]["ev_display"] == "4105/913 ¢"
    assert verified["pool"]["trade_75_55"]["S_display"] == "450/868"
    assert verified["pool"]["trade_75_55"]["excluded_hit_81"] == 45
    assert by_id["nba_2q"]["trade_75_55"]["S_display"] == "158/309"
    assert PATH_STOPS_75 == (25, 30, 35, 40, 45, 50, 55)
    assert MID_STOPS_75 == (33, 37, 43, 47)
    assert verified["pool"]["ledger_rank"][0] == "75/35"
    mid = {row["key"]: row for row in verified["pool"]["mid_paths"]}
    assert list(mid) == ["75/33", "75/37", "75/43", "75/47"]
    assert mid["75/33"]["S_display"] == "637/913"
    assert mid["75/33"]["book_cents"] == 4333
    assert mid["75/33"]["loss_cents"] == 42
    assert mid["75/37"]["S_display"] == "615/913"
    assert mid["75/37"]["book_cents"] == 4051
    assert mid["75/37"]["loss_cents"] == 38
    assert mid["75/43"]["S_display"] == "584/913"
    assert mid["75/43"]["book_cents"] == 4072
    assert mid["75/43"]["loss_cents"] == 32
    assert mid["75/47"]["S_display"] == "556/913"
    assert mid["75/47"]["book_cents"] == 3904
    assert mid["75/47"]["loss_cents"] == 28
    assert all(row["n"] == 913 for row in mid.values())
    assert verified["pool"]["mid_ledger_rank"] == ["75/33", "75/43", "75/37", "75/47"]


def test_first75_mid_stop_tile_cells():
    expected = {
        33: (636, 60, 1, 216),
        37: (614, 82, 1, 216),
        43: (583, 113, 1, 216),
        47: (555, 141, 1, 216),
    }
    for stop, cells in expected.items():
        assert ladder_cells_75(stop, "derived_four") == cells


def test_first75_barrier_55_before_81():
    expected = {
        "nba_2q": (309, 9, 235, 74, (157, 78, 1, 73)),
        "nba_3q": (241, 17, 179, 62, (130, 49, 0, 62)),
        "ncaab_h1_2": (193, 11, 146, 47, (91, 55, 0, 47)),
        "ncaab_h2_1": (125, 8, 103, 22, (71, 32, 0, 22)),
    }
    for lock in BARRIER_55_75:
        assert (lock.n, lock.excluded_hit_86, lock.W, lock.L, lock.cells) == expected[lock.partition_id]
    assert BARRIER_55_POOL_N_75 == 868
    assert BARRIER_55_POOL_EXCL_75 == 45
    assert BARRIER_55_POOL_N_75 + BARRIER_55_POOL_EXCL_75 == 913
    assert BARRIER_55_POOL_CELLS_75 == (449, 214, 1, 204)


def test_first80_universe_unchanged_by_first75_page():
    body = handle_universe()
    assert body["pool"]["n"] == 936
    assert body["rule"] == "FIRST80"
    assert body["pool"]["trade_80_40"]["S_display"] == "700/936"


def test_first75_tampered_lock_mismatches():
    bad = (replace(PARTITIONS_75[0], n=317, L=75),) + PARTITIONS_75[1:]
    with pytest.raises(ChoosinTexasError) as exc:
        verify_locks_75(partitions=bad)
    assert exc.value.code == "LOCK_MISMATCH"


def test_first75_missing_tables_is_data_required(tmp_path):
    missing = tmp_path / "no-tables.json"
    with pytest.raises(ChoosinTexasError) as exc:
        verify_locks_75(tables_path=missing)
    assert exc.value.code == "DATA_REQUIRED"


def test_handle_universe_75():
    health = handle_health()
    assert "choosin_texas_universe_75" in health["capabilities"]
    assert "choosin_texas_nba_path_75" in health["capabilities"]
    body = handle_universe_75()
    assert body["status"] == "OBSERVED"
    assert body["live_execution"] is False
    assert body["rule"] == "FIRST75"
    assert body["gain_cents"] == 25
    assert body["entry_cents"] == 75
    assert body["entry_cap_cents"] == 81
    assert body["pool"]["n"] == 913
    assert body["pool"]["terminal"]["p_display"] == "696/913"
    assert body["complement"]["identity"] == "1126 = 913 + 213"
    assert "FIRST75 913 ≠ FIRST80 936" in body["disclaimers"]
    assert body["pool"]["ledger_rank"][0] == "75/35"
    assert body["mid_stops"] == [33, 37, 43, 47]
    assert body["path_stops"] == [25, 30, 35, 40, 45, 50, 55]
    assert [row["key"] for row in body["pool"]["mid_paths"]] == [
        "75/33",
        "75/37",
        "75/43",
        "75/47",
    ]


def test_nba_path_75():
    path = build_nba_path_75()
    assert path["status"] == "OBSERVED"
    assert path["n"] == 576
    assert path["n_t40"] == 200
    assert path["n_survive"] == 376
    assert path["rule"] == "FIRST75"


def test_terminal_api_universe_75():
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import terminal_api

    client = TestClient(terminal_api.app)
    health = client.get("/health").json()
    assert "choosin_texas_universe_75" in health["capabilities"]
    desk = client.get("/choosin-texas/health").json()
    assert "choosin_texas_universe_75" in desk["capabilities"]
    res = client.get("/choosin-texas/universe-75")
    assert res.status_code == 200
    payload = res.json()
    assert payload["status"] == "OBSERVED"
    assert payload["pool"]["W"] == 696
    assert payload["pool"]["trade_75_40"]["S_display"] == "601/913"
    assert payload["pool"]["paths"][0]["key"] == "75/25"
    nba = client.get("/choosin-texas/nba-path-75")
    assert nba.status_code == 200
    assert nba.json()["n"] == 576
    first80 = client.get("/choosin-texas/universe").json()
    assert first80["pool"]["n"] == 936


def test_frontend_texas_75_does_not_compute_rates():
    if not FRONTEND_APP.is_file():
        pytest.skip("frontend not scaffolded yet")
    app = FRONTEND_APP.read_text(encoding="utf-8")
    assert "#/texas-75" in app
    assert "Texas (75)" in app
    page = FRONTEND_TEXAS75.read_text(encoding="utf-8")
    assert "fetchUniverse75" in page
    assert "fetchNbaPath75" in page
    assert "ev_per_trade_display" in page
    assert "* 100" not in page
    assert "20S" not in page
    assert "25S" not in page
    assert "mid_paths" in page
    assert "75/33" in page
    assert "80/33" not in page
