"""FIRST80 80/60 on the same derived four as 80/40. N stays 936."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from roller.choosin_texas.api import handle_health, handle_universe, handle_universe_60
from roller.choosin_texas.locks import BARRIER_60, PARTITIONS, PATH_STOPS, POOL_N, STOP_60_CENTS
from roller.choosin_texas.models import ChoosinTexasError
from roller.choosin_texas.texas60 import build_universe_60, verify_universe_60


REPO = Path(__file__).resolve().parents[2]
FRONTEND_APP = REPO / "frontend" / "choosin-texas" / "src" / "App.tsx"
FRONTEND_TEXAS60 = REPO / "frontend" / "choosin-texas" / "src" / "Texas60.tsx"


def test_t60_cells_match_csv_and_nest_under_50():
    verified = verify_universe_60()
    assert verified["pool_cells"] == (568, 218, 0, 150)
    assert sum(verified["pool_cells"]) == POOL_N
    assert BARRIER_60["derived_four"] == (568, 218, 0, 150)
    assert STOP_60_CENTS == 60
    expected = {
        "nba_2q": (188, 79, 0, 47),
        "nba_3q": (186, 52, 0, 52),
        "ncaab_h1_2": (109, 54, 0, 30),
        "ncaab_h2_1": (85, 33, 0, 21),
    }
    for lock in PARTITIONS:
        assert BARRIER_60[lock.partition_id] == expected[lock.partition_id]
        assert sum(BARRIER_60[lock.partition_id]) == lock.n
    assert sum(cells[0] for cells in expected.values()) == 568


def test_80_60_ev_on_full_book_and_40_page_unchanged():
    body = build_universe_60()
    trade = body["pool"]["trade_80_60"]
    assert body["status"] == "OBSERVED"
    assert body["live_execution"] is False
    assert body["submits"] is False
    assert body["rule"] == "FIRST80"
    assert body["pool"]["n"] == 936
    assert body["entry_cents"] == 80
    assert body["stop_cents"] == 60
    assert body["gain_cents"] == 20
    assert body["loss_cents"] == 20
    assert trade["n"] == 936
    assert trade["S_display"] == "568/936"
    assert trade["ev_display"] == "500/117 ¢"
    assert trade["book_cents"] == 4000
    assert trade["loss_cents"] == 20
    assert trade["gain_cents"] == 20
    assert trade["cells"] == {
        "W_and_not_T60": 568,
        "W_and_T60": 218,
        "L_and_not_T60": 0,
        "L_and_T60": 150,
    }
    by_id = {row["partition_id"]: row["trade_80_60"] for row in body["partitions"]}
    assert by_id["nba_2q"]["S_display"] == "188/314"
    assert by_id["nba_2q"]["book_cents"] == 1240
    assert by_id["nba_3q"]["S_display"] == "186/290"
    assert by_id["nba_3q"]["book_cents"] == 1640
    assert by_id["ncaab_h1_2"]["S_display"] == "109/193"
    assert by_id["ncaab_h1_2"]["book_cents"] == 500
    assert by_id["ncaab_h2_1"]["S_display"] == "85/139"
    assert by_id["ncaab_h2_1"]["book_cents"] == 620
    assert all(row["trade_80_60"]["n"] == row["n"] for row in body["partitions"])
    assert body["anchor_80_40"]["n"] == 936
    assert body["anchor_80_40"]["S_display"] == "700/936"
    band = {row["key"]: row for row in body["pool"]["band"]}
    assert list(band) == ["80/55", "80/60", "80/65"]
    assert body["pool"]["band_rank"] == ["80/60", "80/65", "80/55"]
    assert band["80/55"]["n"] == 936
    assert band["80/55"]["S_display"] == "603/936"
    assert band["80/55"]["ev_display"] == "415/104 ¢"
    assert band["80/55"]["book_cents"] == 3735
    assert band["80/55"]["loss_cents"] == 25
    assert band["80/65"]["S_display"] == "515/936"
    assert band["80/65"]["ev_display"] == "3985/936 ¢"
    assert band["80/65"]["book_cents"] == 3985
    assert band["80/65"]["loss_cents"] == 15
    t65 = body["gap"]["t65"]["pool"]
    assert t65["n"] == 421
    assert t65["separate_print"]["display"] == "306/421"
    assert t65["same_bar_at_or_below_60"]["display"] == "115/421"
    assert t65["separate_then_60"]["display"] == "253/306"
    assert t65["separate_held_above_60"]["display"] == "53/306"
    t60 = body["gap"]["t60"]["pool"]
    assert t60["n"] == 368
    assert t60["separate_print"]["display"] == "251/368"
    assert t60["same_bar_at_or_below_55"]["display"] == "117/368"
    assert t60["continued_to_55"]["display"] == "333/368"
    assert t60["never_printed_55"]["display"] == "35/368"
    clocks = {row["slice"]: row for row in body["clocks"]}
    assert clocks["Q2"]["n_t60"] == 126
    assert clocks["Q3"]["n_t60"] == 104
    q2_means = {row["period"]: row for row in clocks["Q2"]["mean_remaining"]}
    assert q2_means["Q3"]["n"] == 66
    assert q2_means["Q3"]["clock_display"] == "05:58"
    q3_means = {row["period"]: row for row in clocks["Q3"]["mean_remaining"]}
    assert q3_means["Q3"]["n"] == 40
    assert q3_means["Q3"]["clock_display"] == "02:21"
    assert q3_means["Q4"]["n"] == 64
    first80 = handle_universe()
    assert first80["pool"]["n"] == 936
    assert first80["pool"]["trade_80_40"]["S_display"] == "700/936"
    assert [row["key"] for row in first80["pool"]["paths"]] == [
        "80/25",
        "80/30",
        "80/35",
        "80/40",
        "80/45",
        "80/50",
        "80/55",
    ]
    assert 60 not in PATH_STOPS
    assert first80["pool"]["paths"][6]["n"] == 905


def test_tampered_t60_lock_mismatches():
    bad = dict(BARRIER_60)
    bad["nba_2q"] = (189, 78, 0, 47)
    with pytest.raises(ChoosinTexasError) as exc:
        verify_universe_60(cells=bad)
    assert exc.value.code == "LOCK_MISMATCH"


def test_missing_csv_is_data_required(tmp_path):
    missing = tmp_path / "no-asked-six.csv"
    with pytest.raises(ChoosinTexasError) as exc:
        verify_universe_60(csv_path=missing)
    assert exc.value.code == "DATA_REQUIRED"


def test_handle_and_terminal_api_universe_60():
    health = handle_health()
    assert "choosin_texas_universe_60" in health["capabilities"]
    body = handle_universe_60()
    assert body["page"] == "80/60"
    assert body["pool"]["trade_80_60"]["S_display"] == "568/936"

    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import terminal_api

    client = TestClient(terminal_api.app)
    desk = client.get("/health").json()
    assert "choosin_texas_universe_60" in desk["capabilities"]
    choosin = client.get("/choosin-texas/health").json()
    assert "choosin_texas_universe_60" in choosin["capabilities"]
    res = client.get("/choosin-texas/universe-60")
    assert res.status_code == 200
    payload = res.json()
    assert payload["status"] == "OBSERVED"
    assert payload["pool"]["trade_80_60"]["ev_display"] == "500/117 ¢"
    assert payload["pool"]["trade_80_60"]["n"] == 936
    first80 = client.get("/choosin-texas/universe")
    assert first80.status_code == 200
    assert first80.json()["pool"]["trade_80_40"]["S_display"] == "700/936"


def test_frontend_80_60_does_not_compute_rates():
    if not FRONTEND_APP.is_file():
        pytest.skip("frontend not scaffolded yet")
    app = FRONTEND_APP.read_text(encoding="utf-8")
    assert "#/texas-60" in app
    assert "80/60" in app
    page = FRONTEND_TEXAS60.read_text(encoding="utf-8")
    assert "fetchUniverse60" in page
    assert "ev_per_trade_display" in page
    assert "W_and_not_T60" in page
    assert "* 100" not in page
    assert "/ n" not in page
    assert "20S" not in page
    assert "successes /" not in page
