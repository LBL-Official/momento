"""Choosin Texas FIRST80 80/40 four-partition locks. Integers are the authority."""

from __future__ import annotations

import csv
import json
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from roller.choosin_texas.api import (
    handle_book,
    handle_dallas,
    handle_health,
    handle_nba_path,
    handle_universe,
)
from roller.choosin_texas.book import BOOK_ID, default_book_json
from roller.choosin_texas.locks import (
    ASKED_SIX_CELLS,
    ASKED_SIX_N,
    BARRIER_55,
    BARRIER_55_POOL_CELLS,
    BARRIER_55_POOL_EXCL,
    BARRIER_55_POOL_N,
    BARRIER_CELLS,
    BARRIER_STOPS,
    MID_STOPS,
    NBA_PATH_N,
    NBA_SLICE_T40,
    NBA_SLICE_T40_LOSE,
    NBA_SLICE_T40_WIN,
    NBA_SURVIVE_N,
    NBA_T40_LOSE_N,
    NBA_T40_N,
    NBA_T40_WIN_N,
    PARTITIONS,
    PATH_STOPS,
    POOL_CELLS,
    POOL_L,
    POOL_N,
    POOL_W,
    WNBA_UNION_N,
    ladder_cells,
)
from roller.choosin_texas.models import ChoosinTexasError
from roller.choosin_texas.rates import assert_identities, partition_payload, rates_from_cells
from roller.choosin_texas.sources import (
    default_asked_six_csv,
    default_tables_json,
    load_csv_barrier_55,
    load_csv_barriers,
    load_csv_cells,
)
from roller.choosin_texas.verify import verify_locks
from roller.superasi.seed import LOCK_CELLS, LOCK_N


REPO = Path(__file__).resolve().parents[2]
FRONTEND_APP = REPO / "frontend" / "choosin-texas" / "src" / "App.tsx"
FRONTEND_TEXAS = REPO / "frontend" / "choosin-texas" / "src" / "Texas.tsx"
FRONTEND_DALLAS = REPO / "frontend" / "choosin-texas" / "src" / "Dallas.tsx"
FRONTEND_BOOK = REPO / "frontend" / "choosin-texas" / "src" / "Book.tsx"


def test_lock_integers_match_tables_md():
    expected = {
        "nba_2q": (314, 267, 47, (239, 28, 0, 47)),
        "nba_3q": (290, 238, 52, (211, 27, 0, 52)),
        "ncaab_h1_2": (193, 163, 30, (142, 21, 0, 30)),
        "ncaab_h2_1": (139, 118, 21, (108, 10, 0, 21)),
    }
    for lock in PARTITIONS:
        assert (lock.n, lock.W, lock.L, lock.cells) == expected[lock.partition_id]
        assert lock.lose_no == 0


def test_identities_and_s_not_terminal_p():
    for lock in PARTITIONS:
        assert_identities(
            lock.n,
            lock.W,
            lock.L,
            lock.win_no,
            lock.win_t40,
            lock.lose_no,
            lock.lose_t40,
            label=lock.partition_id,
        )
        body = rates_from_cells(
            lock.n,
            lock.W,
            lock.L,
            lock.win_no,
            lock.win_t40,
            lock.lose_no,
            lock.lose_t40,
            label=lock.partition_id,
        )
        assert body["s_L"]["numer"] == 0
        assert body["terminal"]["p"]["numer"] != body["trade_80_40"]["S"]["numer"]
        assert body["trade_80_40"]["S"]["numer"] == lock.win_no
        assert body["joint"]["numer"] == lock.win_no


def test_derived_four_pool():
    assert POOL_N == 936
    assert POOL_W == 786
    assert POOL_L == 150
    assert POOL_CELLS == (700, 86, 0, 150)
    assert sum(p.n for p in PARTITIONS) == POOL_N
    assert sum(p.W for p in PARTITIONS) == POOL_W
    assert sum(p.win_no for p in PARTITIONS) == POOL_CELLS[0]


def test_asked_six_complement():
    assert ASKED_SIX_N == 1182
    assert WNBA_UNION_N == 246
    assert POOL_N + WNBA_UNION_N == ASKED_SIX_N
    assert ASKED_SIX_CELLS == (883, 108, 0, 191)
    assert LOCK_N == ASKED_SIX_N
    assert tuple(LOCK_CELLS) == ASKED_SIX_CELLS
    wnba = ASKED_SIX_CELLS[0] - POOL_CELLS[0]
    assert wnba == 183


def test_barrier_55_before_86_locks():
    expected = {
        "nba_2q": (311, 3, 265, 46, (202, 63, 0, 46)),
        "nba_3q": (272, 18, 222, 50, (177, 45, 0, 50)),
        "ncaab_h1_2": (187, 6, 158, 29, (115, 43, 0, 29)),
        "ncaab_h2_1": (135, 4, 114, 21, (85, 29, 0, 21)),
    }
    for lock in BARRIER_55:
        assert (lock.n, lock.excluded_hit_86, lock.W, lock.L, lock.cells) == expected[lock.partition_id]
        assert lock.lose_no == 0
        assert lock.n + lock.excluded_hit_86 == {
            "nba_2q": 314,
            "nba_3q": 290,
            "ncaab_h1_2": 193,
            "ncaab_h2_1": 139,
        }[lock.partition_id]
    assert BARRIER_55_POOL_N == 905
    assert BARRIER_55_POOL_EXCL == 31
    assert BARRIER_55_POOL_N + BARRIER_55_POOL_EXCL == 936
    assert BARRIER_55_POOL_CELLS == (579, 180, 0, 146)
    csv_55 = load_csv_barrier_55()["partitions"]
    for lock in BARRIER_55:
        row = csv_55[lock.partition_id]
        assert row["n"] == lock.n
        assert row["excluded_hit_86"] == lock.excluded_hit_86
        assert (row["win_no"], row["win_t55"], row["lose_no"], row["lose_t55"]) == lock.cells


def test_tables_json_and_csv_agree_with_locks():
    verified = verify_locks()
    assert verified["status"] == "OBSERVED"
    assert verified["pool"]["n"] == 936
    assert verified["pool"]["role"] == "derived_four"
    by_id = {row["partition_id"]: row for row in verified["partitions"]}
    assert by_id["nba_2q"]["n"] == 314
    assert by_id["nba_2q"]["terminal"]["p_display"] == "267/314"
    assert by_id["nba_2q"]["terminal"]["p_pct_display"] == "85.0318%"
    assert by_id["nba_2q"]["trade_80_40"]["S_display"] == "239/314"
    assert by_id["nba_2q"]["trade_80_40"]["S_pct_display"] == "76.1146%"
    assert by_id["nba_3q"]["n"] == 290
    assert by_id["ncaab_h1_2"]["n"] == 193
    assert by_id["ncaab_h2_1"]["n"] == 139
    assert by_id["nba_2q"]["trade_80_55"]["S_display"] == "202/311"
    assert by_id["nba_3q"]["trade_80_55"]["S_display"] == "177/272"
    assert by_id["ncaab_h1_2"]["trade_80_55"]["S_display"] == "115/187"
    assert by_id["ncaab_h2_1"]["trade_80_55"]["S_display"] == "85/135"
    assert verified["pool"]["trade_80_55"]["S_display"] == "579/905"
    assert verified["pool"]["trade_80_55"]["excluded_hit_86"] == 31
    csv_body = load_csv_cells()
    assert csv_body["asked_six_n"] == 1182
    assert csv_body["wnba_n"] == 246


def test_published_tables_pct_regression():
    tables = json.loads(default_tables_json().read_text(encoding="utf-8"))
    rows = {
        (row["sport"], row["slice"]): row
        for row in tables["rows"]
        if row.get("rule") == "FIRST80" and row.get("role") == "asked_six"
    }
    for lock in PARTITIONS:
        published = rows[(lock.sport, lock.slice)]
        payload = partition_payload(lock)
        assert float(payload["terminal"]["p_pct_display"].rstrip("%")) == pytest.approx(
            published["p_pct"], abs=0.00005
        )


def test_tampered_lock_mismatches():
    bad = (replace(PARTITIONS[0], n=313, L=46),) + PARTITIONS[1:]
    with pytest.raises(ChoosinTexasError) as exc:
        verify_locks(partitions=bad)
    assert exc.value.code == "LOCK_MISMATCH"


def test_tampered_csv_mismatches(tmp_path):
    src = default_asked_six_csv()
    dest = tmp_path / "asked_six.csv"
    with src.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        fieldnames = reader.fieldnames
    assert fieldnames is not None
    kept = [row for row in rows if not (row.get("sport") == "NBA" and row.get("slice") == "Q2")]
    with dest.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(kept)
    with pytest.raises(ChoosinTexasError) as exc:
        verify_locks(csv_path=dest)
    assert exc.value.code == "LOCK_MISMATCH"


def test_missing_tables_is_data_required(tmp_path):
    missing = tmp_path / "no-tables.json"
    with pytest.raises(ChoosinTexasError) as exc:
        verify_locks(tables_path=missing)
    assert exc.value.code == "DATA_REQUIRED"


def test_barrier_ladder_cells_and_nest():
    expected_pool = {
        25: (746, 40, 0, 150),
        30: (736, 50, 0, 150),
        35: (721, 65, 0, 150),
        40: (700, 86, 0, 150),
        45: (680, 106, 0, 150),
        50: (650, 136, 0, 150),
    }
    for stop, cells in expected_pool.items():
        assert ladder_cells(stop, "derived_four") == cells
    for stop in BARRIER_STOPS:
        assert sum(BARRIER_CELLS[stop][lock.partition_id][0] for lock in PARTITIONS) == BARRIER_CELLS[stop]["derived_four"][0]
    csv_body = load_csv_barriers()["partitions"]
    for stop in (25, 30, 35, 40, 45, 50):
        for lock in PARTITIONS:
            row = csv_body[stop][lock.partition_id]
            assert (
                row["win_no"],
                row["win_tx"],
                row["lose_no"],
                row["lose_tx"],
            ) == ladder_cells(stop, lock.partition_id)
            assert row["lose_no"] == 0
    # Nested: survivors of a tighter/deeper stop contain survivors of a higher print.
    s = {stop: ladder_cells(stop, "derived_four")[0] for stop in (25, 30, 33, 35, 37, 40, 43, 45, 47, 50)}
    assert s[25] >= s[30] >= s[33] >= s[35] >= s[37] >= s[40] >= s[43] >= s[45] >= s[47] >= s[50]


def test_path_ev_fractions():
    verified = verify_locks()
    expected = {
        "80/25": ("746/936", "745/156 ¢", 4470),
        "80/30": ("736/936", "590/117 ¢", 4720),
        "80/35": ("721/936", "365/72 ¢", 4745),
        "80/40": ("700/936", "190/39 ¢", 4560),
        "80/45": ("680/936", "580/117 ¢", 4640),
        "80/50": ("650/936", "85/18 ¢", 4420),
        "80/55": ("579/905", "686/181 ¢", 3430),
    }
    by_key = {row["key"]: row for row in verified["pool"]["paths"]}
    assert list(by_key) == ["80/25", "80/30", "80/35", "80/40", "80/45", "80/50", "80/55"]
    for key, (s_display, ev_display, book) in expected.items():
        assert by_key[key]["S_display"] == s_display
        assert by_key[key]["ev_display"] == ev_display
        assert by_key[key]["book_cents"] == book
    assert verified["pool"]["ledger_rank"] == [
        "80/35",
        "80/30",
        "80/45",
        "80/40",
        "80/25",
        "80/50",
        "80/55",
    ]
    assert verified["pool"]["trade_80_40"]["ev_display"] == "190/39 ¢"
    assert verified["pool"]["trade_80_55"]["ev_display"] == "686/181 ¢"
    assert by_key["80/55"]["n"] == 905
    assert by_key["80/40"]["n"] == 936
    assert PATH_STOPS == (25, 30, 35, 40, 45, 50, 55)
    assert MID_STOPS == (33, 37, 43, 47)
    mid = {row["key"]: row for row in verified["pool"]["mid_paths"]}
    assert list(mid) == ["80/33", "80/37", "80/43", "80/47"]
    assert mid["80/33"]["S_display"] == "727/936"
    assert mid["80/33"]["ev_display"] == "4717/936 ¢"
    assert mid["80/33"]["book_cents"] == 4717
    assert mid["80/33"]["loss_cents"] == 47
    assert mid["80/37"]["S_display"] == "714/936"
    assert mid["80/37"]["book_cents"] == 4734
    assert mid["80/37"]["loss_cents"] == 43
    assert mid["80/43"]["S_display"] == "692/936"
    assert mid["80/43"]["book_cents"] == 4812
    assert mid["80/43"]["loss_cents"] == 37
    assert mid["80/47"]["S_display"] == "667/936"
    assert mid["80/47"]["book_cents"] == 4463
    assert mid["80/47"]["loss_cents"] == 33
    assert all(row["n"] == 936 for row in mid.values())
    assert verified["pool"]["mid_ledger_rank"] == ["80/43", "80/37", "80/33", "80/47"]


def test_mid_stop_tile_cells_match_csv():
    expected = {
        33: {
            "nba_2q": (247, 20, 0, 47),
            "nba_3q": (222, 16, 0, 52),
            "ncaab_h1_2": (147, 16, 0, 30),
            "ncaab_h2_1": (111, 7, 0, 21),
            "derived_four": (727, 59, 0, 150),
        },
        37: {
            "nba_2q": (243, 24, 0, 47),
            "nba_3q": (218, 20, 0, 52),
            "ncaab_h1_2": (144, 19, 0, 30),
            "ncaab_h2_1": (109, 9, 0, 21),
            "derived_four": (714, 72, 0, 150),
        },
        43: {
            "nba_2q": (235, 32, 0, 47),
            "nba_3q": (210, 28, 0, 52),
            "ncaab_h1_2": (141, 22, 0, 30),
            "ncaab_h2_1": (106, 12, 0, 21),
            "derived_four": (692, 94, 0, 150),
        },
        47: {
            "nba_2q": (224, 43, 0, 47),
            "nba_3q": (207, 31, 0, 52),
            "ncaab_h1_2": (131, 32, 0, 30),
            "ncaab_h2_1": (105, 13, 0, 21),
            "derived_four": (667, 119, 0, 150),
        },
    }
    csv_body = load_csv_barriers()["partitions"]
    for stop, by_id in expected.items():
        assert ladder_cells(stop, "derived_four") == by_id["derived_four"]
        for partition_id, cells in by_id.items():
            assert ladder_cells(stop, partition_id) == cells
            if partition_id == "derived_four":
                continue
            row = csv_body[stop][partition_id]
            assert (row["win_no"], row["win_tx"], row["lose_no"], row["lose_tx"]) == cells
            assert row["n"] == {"nba_2q": 314, "nba_3q": 290, "ncaab_h1_2": 193, "ncaab_h2_1": 139}[partition_id]


def test_nba_path_clock_and_scatter():
    body = handle_nba_path()
    assert body["status"] == "OBSERVED"
    assert body["n"] == NBA_PATH_N == 604
    assert body["n_t40"] == NBA_T40_N == 154
    assert body["n_survive"] == NBA_SURVIVE_N == 450
    assert len(body["scatter"]["points"]) == 604
    clocks = {row["slice"]: row for row in body["clocks"]}
    assert clocks["Q2"]["n_t40"] == NBA_SLICE_T40["Q2"] == 75
    assert clocks["Q3"]["n_t40"] == NBA_SLICE_T40["Q3"] == 79
    assert sum(bin_row["n"] for bin_row in clocks["Q2"]["bins"]) == 75
    assert sum(bin_row["n"] for bin_row in clocks["Q3"]["bins"]) == 79
    assert body["alignment"]["model"] == "PERIOD_BOUNDED_LINEAR_GAME_CLOCK"
    survive = [pt for pt in body["scatter"]["points"] if not pt["t40"]]
    t40 = [pt for pt in body["scatter"]["points"] if pt["t40"]]
    assert len(survive) == 450
    assert len(t40) == 154
    assert all(pt["t40_margin"] is None for pt in survive)
    assert all(pt["t40_margin"] is not None for pt in t40)
    assert body["margins"]["t40"]["t40_time"]["mean"]["numer"] == -64
    assert body["margins"]["t40"]["t40_time"]["mean"]["denom"] == 77


def _assert_dallas_cuts(cuts: dict, n: int) -> None:
    assert sum(int(row["n"]) for row in cuts["lead_80"]) == n
    assert sum(int(row["n"]) for row in cuts["pregame"]) == n
    assert sum(int(cell["n"]) for cell in cuts["cross"]["cells"]) == n
    for row in list(cuts["lead_80"]) + list(cuts["pregame"]) + list(cuts["cross"]["cells"]):
        win = int(row["t40_win"]["count"])
        lose = int(row["t40_lose"]["count"])
        survive = int(row["survive"]["count"])
        t40 = int(row["t40"]["count"])
        assert win + lose + survive == int(row["n"])
        assert t40 == win + lose
        assert row["hover_lines"]


def test_dallas_cohorts_and_snapshots():
    body = handle_dallas()
    assert body["status"] == "OBSERVED"
    assert body["n"] == 604
    assert body["n_survive"] == NBA_SURVIVE_N == 450
    assert body["n_t40_win"] == NBA_T40_WIN_N == 55
    assert body["n_t40_lose"] == NBA_T40_LOSE_N == 99
    assert body["rates"]["t40"]["display"] == "154/604"
    assert body["rates"]["t40_win"]["display"] == "55/604"
    assert body["rates"]["t40_lose"]["display"] == "99/604"
    by_slice = {row["slice"]: row for row in body["slices"]}
    assert by_slice["Q2"]["n"] == 314
    assert by_slice["Q3"]["n"] == 290
    assert by_slice["Q2"]["rates"]["t40_win"]["count"] == NBA_SLICE_T40_WIN["Q2"]
    assert by_slice["Q3"]["rates"]["t40_lose"]["count"] == NBA_SLICE_T40_LOSE["Q3"]
    assert len(by_slice["Q2"]["games"]) == 314
    assert len(by_slice["Q2"]["collapse"]) == 75
    assert len(by_slice["Q3"]["collapse"]) == 79
    assert len(by_slice["Q2"]["snapshots"]) == 314 * 3 + 75
    assert all(game["pregame_cents"] >= 0 for game in by_slice["Q2"]["games"])
    labels = {snap["label"] for snap in by_slice["Q2"]["snapshots"]}
    assert labels == {"PREGAME", "FIRST80", "T40", "FINAL"}
    assert all(game["hover_lines"] for game in by_slice["Q2"]["games"])
    assert all(snap["hover_lines"] for snap in by_slice["Q2"]["snapshots"])
    assert all(row["hover_lines"] for row in by_slice["Q2"]["collapse"])
    assert by_slice["Q2"]["game_chart"]["x_ticks"]
    assert by_slice["Q2"]["game_chart"]["y_ticks"]
    assert by_slice["Q2"]["snapshot_chart"]["x_label"]
    assert by_slice["Q2"]["collapse_chart"]["y_label"]
    for slice_row in body["slices"]:
        _assert_dallas_cuts(slice_row["cuts"], slice_row["n"])
    _assert_dallas_cuts(body["cuts"], 604)
    assert {row["key"] for row in body["cuts"]["pregame"]} <= {
        "le30",
        "31_35",
        "36_40",
        "41_45",
        "46_50",
        "51_55",
        "56_60",
        "61_65",
        "66_70",
        "ge71",
    }


def test_book_reconstruct_matches_library_lock():
    assert default_book_json().is_file()
    body = handle_book()
    assert body["status"] == "OBSERVED"
    assert body["live_execution"] is False
    assert body["submits"] is False
    assert body["enable_live_trading"] is False
    assert body["book_id"] == BOOK_ID
    assert body["registered"]["filters"] == []
    assert body["registered"]["slice"] == "Q2"
    assert body["registered"]["season_phase"] == "REGULAR_SEASON"
    assert body["registered"]["stop_cents"] == 40
    assert body["registered"]["contracts"] == 1
    by_id = {row["tape_id"]: row for row in body["tapes"]}
    assert by_id["nba_2q3q"]["n"] == 604
    assert by_id["nba_2q3q"]["s_display"] == "450/604"
    assert by_id["nba_2q3q"]["book_cents"] == 2840
    assert by_id["ncaab_h12_h21"]["n"] == 332
    assert by_id["ncaab_h12_h21"]["s_display"] == "250/332"
    assert by_id["ncaab_h12_h21"]["book_cents"] == 1720
    assert by_id["nba_2q_regular"]["n"] == 280
    assert by_id["nba_2q_regular"]["s_display"] == "218/280"
    assert by_id["nba_2q_regular"]["book_cents"] == 1880
    assert by_id["nba_2q_regular"]["ev_per_trade_display"] == "+6.7143¢ / trade"
    assert by_id["nba_2q_regular"]["cross_4_6_ge71"]["book_cents"] == -120
    assert by_id["ncaab_h12_h21"]["cross_4_6_ge71"]["n"] == 32
    assert body["baseline"]["book_cents"] == 1880
    assert any(row["verdict"] == "reverses" for row in body["hold_reverse"])
    assert body["verification"]["status"] == "OBSERVED"


def test_handler_observed_only_when_locks_hold():
    health = handle_health()
    assert health["ok"] is True
    assert health["live_execution"] is False
    assert health["capability"] == "choosin_texas_universe"
    body = handle_universe()
    assert body["status"] == "OBSERVED"
    assert body["verification"]["status"] == "OBSERVED"
    assert body["pool"]["n"] == 936
    assert body["live_execution"] is False
    assert "asked-six (1182) ≠ NBA+NCAAB four (936)" in body["disclaimers"]
    assert [row["key"] for row in body["pool"]["paths"]] == [
        "80/25",
        "80/30",
        "80/35",
        "80/40",
        "80/45",
        "80/50",
        "80/55",
    ]
    assert [row["key"] for row in body["pool"]["mid_paths"]] == [
        "80/33",
        "80/37",
        "80/43",
        "80/47",
    ]
    assert body["mid_stops"] == [33, 37, 43, 47]
    assert body["path_stops"] == [25, 30, 35, 40, 45, 50, 55]
    assert body["pool"]["paths"][2]["ev_display"] == "365/72 ¢"


def test_terminal_api_mount():
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import terminal_api

    client = TestClient(terminal_api.app)
    health = client.get("/health").json()
    assert "choosin_texas_universe" in health["capabilities"]
    assert "choosin_texas_universe_75" in health["capabilities"]
    assert "choosin_texas_dallas" in health["capabilities"]
    assert "choosin_texas_book" in health["capabilities"]
    desk = client.get("/choosin-texas/health").json()
    assert desk["product"] == "Choosin Texas"
    universe = client.get("/choosin-texas/universe")
    assert universe.status_code == 200
    payload = universe.json()
    assert payload["status"] == "OBSERVED"
    assert payload["pool"]["W"] == 786
    assert payload["pool"]["trade_80_40"]["S_display"] == "700/936"
    assert payload["pool"]["trade_80_55"]["S_display"] == "579/905"
    assert payload["pool"]["paths"][0]["key"] == "80/25"
    nba_path = client.get("/choosin-texas/nba-path")
    assert nba_path.status_code == 200
    nba = nba_path.json()
    assert nba["n"] == 604
    assert nba["n_t40"] == 154
    dallas = client.get("/choosin-texas/dallas")
    assert dallas.status_code == 200
    assert dallas.json()["n_t40_win"] == 55
    book = client.get("/choosin-texas/book")
    assert book.status_code == 200
    booked = book.json()
    assert booked["book_id"] == "nba_2q_regular_8040_1lot_2026_27"
    assert booked["live_execution"] is False
    assert booked["baseline"]["n"] == 280
    origins = terminal_api.app.user_middleware[0].cls
    assert origins is not None
    text = Path(terminal_api.__file__).read_text(encoding="utf-8")
    assert "http://127.0.0.1:5182" in text


def test_frontend_does_not_compute_rates():
    if not FRONTEND_APP.is_file():
        pytest.skip("frontend not scaffolded yet")
    for path in (FRONTEND_APP, FRONTEND_TEXAS, FRONTEND_DALLAS, FRONTEND_BOOK):
        text = path.read_text(encoding="utf-8")
        assert "* 100" not in text
        assert "/ n" not in text
        assert "successes /" not in text
        assert "W / N" not in text
        assert "20S" not in text
    texas = FRONTEND_TEXAS.read_text(encoding="utf-8")
    assert "fetchNbaPath" in texas
    assert "ev_per_trade_display" in texas
    assert "mid_paths" in texas
    assert "80/33" in texas
    dallas = FRONTEND_DALLAS.read_text(encoding="utf-8")
    assert "fetchDallas" in dallas
    assert "hover_lines" in dallas
    assert "x_ticks" in dallas
    app = FRONTEND_APP.read_text(encoding="utf-8")
    assert "#/dallas" in app
    assert "#/texas-75" in app
    assert "#/texas-77" in app
    assert "#/book" in app
    book = FRONTEND_BOOK.read_text(encoding="utf-8")
    assert "fetchBook" in book
    assert "ev_per_trade_display" in book
    assert "hold_reverse" in book
