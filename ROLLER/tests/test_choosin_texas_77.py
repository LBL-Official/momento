"""Choosin Texas (77) FIRST77 four-partition locks. Integers are the authority."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from roller.choosin_texas.api import handle_health, handle_universe, handle_universe_77
from roller.choosin_texas.locks77 import (
    ASKED_SIX_CELLS_77,
    ASKED_SIX_N_77,
    BARRIER_55_77,
    BARRIER_55_POOL_CELLS_77,
    BARRIER_55_POOL_EXCL_77,
    BARRIER_55_POOL_N_77,
    MID_STOPS_77,
    PARTITIONS_77,
    PATH_STOPS_77,
    ladder_cells_77,
    POOL_CELLS_77,
    POOL_L_77,
    POOL_N_77,
    POOL_W_77,
    WNBA_UNION_CELLS_77,
    WNBA_UNION_N_77,
)
from roller.choosin_texas.models import ChoosinTexasError
from roller.choosin_texas.nba_path77 import build_nba_path_77
from roller.choosin_texas.texas77 import verify_locks_77


REPO = Path(__file__).resolve().parents[2]
FRONTEND_APP = REPO / "frontend" / "choosin-texas" / "src" / "App.tsx"
FRONTEND_TEXAS77 = REPO / "frontend" / "choosin-texas" / "src" / "Texas77.tsx"


def test_first77_lock_integers_from_collected_csv():
    expected = {
        "nba_2q": (324, 250, 74, (218, 32, 1, 73)),
        "nba_3q": (281, 223, 58, (196, 27, 0, 58)),
        "ncaab_h1_2": (188, 153, 35, (131, 22, 0, 35)),
        "ncaab_h2_1": (140, 120, 20, (109, 11, 0, 20)),
    }
    for lock in PARTITIONS_77:
        assert (lock.n, lock.W, lock.L, lock.cells) == expected[lock.partition_id]
    assert sum(p.n for p in PARTITIONS_77) == POOL_N_77 == 933
    assert sum(p.W for p in PARTITIONS_77) == POOL_W_77 == 746
    assert sum(p.L for p in PARTITIONS_77) == POOL_L_77 == 187
    assert POOL_CELLS_77 == (654, 92, 1, 186)
    assert ASKED_SIX_N_77 == 1158
    assert WNBA_UNION_N_77 == 225
    assert POOL_N_77 + WNBA_UNION_N_77 == ASKED_SIX_N_77
    assert ASKED_SIX_CELLS_77 == (813, 114, 1, 230)
    assert WNBA_UNION_CELLS_77 == (159, 22, 0, 44)


def test_first77_s_includes_lose_no_and_is_not_first80():
    verified = verify_locks_77()
    assert verified["status"] == "OBSERVED"
    assert verified["pool"]["n"] == 933
    assert verified["pool"]["rule"] == "FIRST77"
    assert verified["pool"]["trade_77_40"]["S_display"] == "655/933"
    assert verified["pool"]["trade_77_40"]["key"] == "77/40"
    assert verified["pool"]["trade_77_40"]["gain_cents"] == 23
    assert verified["pool"]["trade_77_40"]["loss_cents"] == 37
    assert verified["pool"]["trade_77_40"]["book_cents"] == 4779
    assert verified["pool"]["trade_77_40"]["ev_display"] == "1593/311 ¢"
    assert verified["pool"]["trade_77_40"]["ev_per_trade_display"] == "+5.1222¢ / trade"
    assert "trade_80_40" not in verified["pool"]
    assert "trade_75_40" not in verified["pool"]
    by_id = {row["partition_id"]: row for row in verified["partitions"]}
    assert by_id["nba_2q"]["cells"]["L_and_not_T40"] == 1
    assert by_id["nba_2q"]["trade_77_40"]["S_display"] == "219/324"
    assert by_id["nba_3q"]["n"] == 281
    assert by_id["ncaab_h1_2"]["n"] == 188
    assert by_id["ncaab_h2_1"]["n"] == 140
    assert [row["key"] for row in verified["pool"]["paths"]] == [
        "77/25",
        "77/30",
        "77/35",
        "77/40",
        "77/45",
        "77/50",
        "77/55",
    ]
    assert verified["pool"]["trade_77_55"]["S_display"] == "507/883"
    assert verified["pool"]["trade_77_55"]["excluded_hit_83"] == 50
    assert by_id["nba_2q"]["trade_77_55"]["S_display"] == "176/321"
    assert PATH_STOPS_77 == (25, 30, 35, 40, 45, 50, 55)
    assert MID_STOPS_77 == (33, 37, 43, 47)
    assert verified["pool"]["ledger_rank"][0] == "77/40"
    mid = {row["key"]: row for row in verified["pool"]["mid_paths"]}
    assert list(mid) == ["77/33", "77/37", "77/43", "77/47"]
    assert mid["77/33"]["S_display"] == "684/933"
    assert mid["77/33"]["book_cents"] == 4776
    assert mid["77/33"]["loss_cents"] == 44
    assert mid["77/37"]["S_display"] == "665/933"
    assert mid["77/37"]["book_cents"] == 4575
    assert mid["77/37"]["loss_cents"] == 40
    assert mid["77/43"]["S_display"] == "641/933"
    assert mid["77/43"]["book_cents"] == 4815
    assert mid["77/43"]["loss_cents"] == 34
    assert mid["77/47"]["S_display"] == "616/933"
    assert mid["77/47"]["book_cents"] == 4658
    assert mid["77/47"]["loss_cents"] == 30
    assert all(row["n"] == 933 for row in mid.values())
    assert verified["pool"]["mid_ledger_rank"] == ["77/43", "77/33", "77/47", "77/37"]


def test_first77_mid_stop_tile_cells():
    expected = {
        33: (683, 63, 1, 186),
        37: (664, 82, 1, 186),
        43: (640, 106, 1, 186),
        47: (615, 131, 1, 186),
    }
    for stop, cells in expected.items():
        assert ladder_cells_77(stop, "derived_four") == cells


def test_first77_barrier_55_before_83():
    expected = {
        "nba_2q": (321, 3, 248, 73, (175, 73, 1, 72)),
        "nba_3q": (262, 19, 205, 57, (154, 51, 0, 57)),
        "ncaab_h1_2": (176, 12, 143, 33, (99, 44, 0, 33)),
        "ncaab_h2_1": (124, 16, 106, 18, (78, 28, 0, 18)),
    }
    for lock in BARRIER_55_77:
        assert (lock.n, lock.excluded_hit_86, lock.W, lock.L, lock.cells) == expected[lock.partition_id]
    assert BARRIER_55_POOL_N_77 == 883
    assert BARRIER_55_POOL_EXCL_77 == 50
    assert BARRIER_55_POOL_N_77 + BARRIER_55_POOL_EXCL_77 == 933
    assert BARRIER_55_POOL_CELLS_77 == (506, 196, 1, 180)


def test_first80_and_first75_unchanged_by_first77_page():
    body = handle_universe()
    assert body["pool"]["n"] == 936
    assert body["rule"] == "FIRST80"
    assert body["pool"]["trade_80_40"]["S_display"] == "700/936"
    from roller.choosin_texas.api import handle_universe_75

    body75 = handle_universe_75()
    assert body75["pool"]["n"] == 913
    assert body75["rule"] == "FIRST75"


def test_first77_tampered_lock_mismatches():
    bad = (replace(PARTITIONS_77[0], n=323, L=73),) + PARTITIONS_77[1:]
    with pytest.raises(ChoosinTexasError) as exc:
        verify_locks_77(partitions=bad)
    assert exc.value.code == "LOCK_MISMATCH"


def test_first77_missing_csv_is_data_required(tmp_path):
    missing = tmp_path / "no-first77.csv"
    with pytest.raises(ChoosinTexasError) as exc:
        verify_locks_77(csv_path=missing)
    assert exc.value.code == "DATA_REQUIRED"


def test_handle_universe_77():
    health = handle_health()
    assert "choosin_texas_universe_77" in health["capabilities"]
    assert "choosin_texas_nba_path_77" in health["capabilities"]
    body = handle_universe_77()
    assert body["status"] == "OBSERVED"
    assert body["live_execution"] is False
    assert body["rule"] == "FIRST77"
    assert body["gain_cents"] == 23
    assert body["entry_cents"] == 77
    assert body["entry_cap_cents"] == 83
    assert body["pool"]["n"] == 933
    assert body["pool"]["terminal"]["p_display"] == "746/933"
    assert body["complement"]["identity"] == "1158 = 933 + 225"
    assert "FIRST77 933 ≠ FIRST75 913 ≠ FIRST80 936" in body["disclaimers"]
    assert body["pool"]["ledger_rank"][0] == "77/40"
    assert body["mid_stops"] == [33, 37, 43, 47]
    assert body["path_stops"] == [25, 30, 35, 40, 45, 50, 55]
    assert [row["key"] for row in body["pool"]["mid_paths"]] == [
        "77/33",
        "77/37",
        "77/43",
        "77/47",
    ]


def test_nba_path_77():
    path = build_nba_path_77()
    assert path["status"] == "OBSERVED"
    assert path["n"] == 605
    assert path["n_t40"] == 190
    assert path["n_survive"] == 415
    assert path["rule"] == "FIRST77"


def test_terminal_api_universe_77():
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import terminal_api

    client = TestClient(terminal_api.app)
    health = client.get("/health").json()
    assert "choosin_texas_universe_77" in health["capabilities"]
    desk = client.get("/choosin-texas/health").json()
    assert "choosin_texas_universe_77" in desk["capabilities"]
    res = client.get("/choosin-texas/universe-77")
    assert res.status_code == 200
    payload = res.json()
    assert payload["status"] == "OBSERVED"
    assert payload["pool"]["W"] == 746
    assert payload["pool"]["trade_77_40"]["S_display"] == "655/933"
    assert payload["pool"]["paths"][0]["key"] == "77/25"
    nba = client.get("/choosin-texas/nba-path-77")
    assert nba.status_code == 200
    assert nba.json()["n"] == 605
    first80 = client.get("/choosin-texas/universe").json()
    assert first80["pool"]["n"] == 936
    first75 = client.get("/choosin-texas/universe-75").json()
    assert first75["pool"]["n"] == 913


def test_frontend_texas_77_does_not_compute_rates():
    if not FRONTEND_APP.is_file():
        pytest.skip("frontend not scaffolded yet")
    app = FRONTEND_APP.read_text(encoding="utf-8")
    assert "#/texas-77" in app
    assert "Texas (77)" in app
    page = FRONTEND_TEXAS77.read_text(encoding="utf-8")
    assert "fetchUniverse77" in page
    assert "fetchNbaPath77" in page
    assert "ev_per_trade_display" in page
    assert "* 100" not in page
    assert "20S" not in page
    assert "23S" not in page
    assert "25S" not in page
    assert "mid_paths" in page
    assert "77/33" in page
    assert "80/33" not in page
    assert "75/33" not in page
