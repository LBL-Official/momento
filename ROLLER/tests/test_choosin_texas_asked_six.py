"""Asked-six page + FIRST81 / FIRST83 companion tiles. Integers are the authority."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from roller.choosin_texas.api import handle_asked_six, handle_health, handle_universe, handle_universe_75, handle_universe_77
from roller.choosin_texas.asked_six import build_asked_six
from roller.choosin_texas.locks81 import ASKED_SIX_N_81, POOL_N_81, WNBA_UNION_N_81
from roller.choosin_texas.locks83 import ASKED_SIX_N_83, POOL_N_83, WNBA_UNION_N_83
from roller.choosin_texas.tau_companion import handle_universe_tau


REPO = Path(__file__).resolve().parents[2]
FRONTEND_APP = REPO / "frontend" / "choosin-texas" / "src" / "App.tsx"
FRONTEND_ASKED = REPO / "frontend" / "choosin-texas" / "src" / "AskedSix.tsx"
FRONTEND_COMPANION = REPO / "frontend" / "choosin-texas" / "src" / "CompanionTau.tsx"
FRONTEND_TEXAS = REPO / "frontend" / "choosin-texas" / "src" / "Texas.tsx"
FRONTEND_TEXAS75 = REPO / "frontend" / "choosin-texas" / "src" / "Texas75.tsx"
FRONTEND_TEXAS77 = REPO / "frontend" / "choosin-texas" / "src" / "Texas77.tsx"


def test_asked_six_identities_and_oos():
    body = build_asked_six()
    assert body["status"] == "OBSERVED"
    assert body["page"] == "asked_six"
    assert body["live_execution"] is False
    books = body["books"]
    assert books["FIRST80"]["n"] == 1182
    assert books["FIRST75"]["n"] == 1126
    assert books["FIRST77"]["n"] == 1158
    assert books["FIRST81"]["n"] == ASKED_SIX_N_81 == 1193
    assert books["FIRST83"]["n"] == ASKED_SIX_N_83 == 1243
    assert books["FIRST80"]["identity"] == "1182 = 936 + 246"
    assert books["FIRST75"]["identity"] == "1126 = 913 + 213"
    assert books["FIRST77"]["identity"] == "1158 = 933 + 225"
    assert books["FIRST81"]["identity"] == "1193 = 940 + 253"
    assert books["FIRST83"]["identity"] == "1243 = 973 + 270"
    assert ASKED_SIX_N_81 == POOL_N_81 + WNBA_UNION_N_81
    assert ASKED_SIX_N_83 == POOL_N_83 + WNBA_UNION_N_83
    ids = [row["partition_id"] for row in body["partitions"]]
    assert ids == ["nba_2q", "nba_3q", "ncaab_h1_2", "ncaab_h2_1", "wnba_2q", "wnba_3q"]
    nba2q = {row["partition_id"]: row for row in body["partitions"]}["nba_2q"]
    assert nba2q["books"]["FIRST80"]["n"] == 314
    assert nba2q["books"]["FIRST75"]["n"] == 318
    assert nba2q["books"]["FIRST77"]["n"] == 324
    assert nba2q["books"]["FIRST81"]["n"] == 307
    assert nba2q["books"]["FIRST83"]["n"] == 299
    ncaab = {row["partition_id"]: row for row in body["partitions"]}["ncaab_h1_2"]
    assert "1H second 10" in ncaab["slice_label"]
    assert ncaab["ncaab_window_note"]
    pool80 = body["pool"]["books"]["FIRST80"]
    assert [row["key"] for row in pool80["paths"]] == [
        "80/25",
        "80/30",
        "80/33",
        "80/35",
        "80/37",
        "80/40",
        "80/43",
        "80/45",
        "80/47",
        "80/50",
        "80/55",
    ]
    assert next(row["S_display"] for row in pool80["paths"] if row["key"] == "80/40") == "883/1182"
    pool81 = body["pool"]["books"]["FIRST81"]
    assert next(row["S_display"] for row in pool81["paths"] if row["key"] == "81/40") == "916/1193"
    assert next(row["n"] for row in pool81["paths"] if row["key"] == "81/55") == 1159
    pool83 = body["pool"]["books"]["FIRST83"]
    assert next(row["S_display"] for row in pool83["paths"] if row["key"] == "83/40") == "992/1243"
    oos80 = body["oos"]["books"]["FIRST80"]
    assert oos80["split"]["train_n"] == 418
    assert oos80["split"]["test_n"] == 182
    assert oos80["train"]["pool"]["n"] == 418
    assert oos80["test"]["pool"]["n"] == 182
    ncaab_test = oos80["test"]["slices"]["ncaab_h1_2"]
    assert ncaab_test["status"] == "DATA_REQUIRED"
    assert ncaab_test["n"] == 7
    oos81 = body["oos"]["books"]["FIRST81"]
    assert oos81["split"]["train_n"] == 424
    assert oos81["split"]["test_n"] == 181
    assert oos81["test"]["slices"]["ncaab_h2_1"]["status"] == "DATA_REQUIRED"
    oos83 = body["oos"]["books"]["FIRST83"]
    assert oos83["split"]["train_n"] == 436
    assert oos83["split"]["test_n"] == 185


def test_derived_four_pages_unchanged():
    assert handle_universe()["pool"]["n"] == 936
    assert handle_universe_75()["pool"]["n"] == 913
    assert handle_universe_77()["pool"]["n"] == 933


def test_companion_81_83_derived_four():
    body81 = handle_universe_tau(81)
    assert body81["status"] == "OBSERVED"
    assert body81["pool"]["n"] == 940
    assert body81["rule"] == "FIRST81"
    assert body81["entry_cap_cents"] == 87
    assert [row["key"] for row in body81["pool"]["paths"]][0] == "81/25"
    assert "80/81" not in [row["key"] for row in body81["pool"]["paths"]]
    body83 = handle_universe_tau(83)
    assert body83["pool"]["n"] == 973
    assert body83["entry_cap_cents"] == 89
    assert [row["key"] for row in body83["pool"]["paths"]][5] == "83/40"


def test_health_and_http_asked_six():
    health = handle_health()
    assert "choosin_texas_asked_six" in health["capabilities"]
    assert "choosin_texas_universe_81" in health["capabilities"]
    payload = handle_asked_six()
    assert payload["status"] == "OBSERVED"
    assert payload["pool"]["role"] == "asked_six"

    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import terminal_api

    client = TestClient(terminal_api.app)
    desk = client.get("/choosin-texas/health").json()
    assert "choosin_texas_asked_six" in desk["capabilities"]
    res = client.get("/choosin-texas/asked-six")
    assert res.status_code == 200
    body = res.json()
    assert body["books"]["FIRST80"]["n"] == 1182
    assert body["books"]["FIRST81"]["n"] == 1193
    assert body["books"]["FIRST83"]["n"] == 1243
    u80 = client.get("/choosin-texas/universe").json()
    u75 = client.get("/choosin-texas/universe-75").json()
    u77 = client.get("/choosin-texas/universe-77").json()
    assert u80["pool"]["n"] == 936
    assert u75["pool"]["n"] == 913
    assert u77["pool"]["n"] == 933
    c81 = client.get("/choosin-texas/universe-81")
    c83 = client.get("/choosin-texas/universe-83")
    assert c81.status_code == 200
    assert c83.status_code == 200
    assert c81.json()["pool"]["n"] == 940
    assert c83.json()["pool"]["n"] == 973


def test_frontend_asked_six_does_not_compute():
    app = FRONTEND_APP.read_text(encoding="utf-8")
    assert "#/asked-six" in app
    assert "Asked-six" in app
    page = FRONTEND_ASKED.read_text(encoding="utf-8")
    assert "fetchAskedSix" in page
    assert "ev_per_trade_display" in page
    assert "* 100" not in page
    assert "20S" not in page
    assert "19S" not in page
    companion = FRONTEND_COMPANION.read_text(encoding="utf-8")
    assert "fetchUniverse81" in companion
    assert "fetchUniverse83" in companion
    assert "80/81" not in companion.replace("80/81/83/89", "")
    assert "* 100" not in companion
    for path in (FRONTEND_TEXAS, FRONTEND_TEXAS75, FRONTEND_TEXAS77):
        text = path.read_text(encoding="utf-8")
        assert "CompanionTau" in text
