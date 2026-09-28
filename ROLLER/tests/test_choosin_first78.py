"""Synthetic FIRST78 desk checks. The warehouse scan is not required here."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "research/first78_67_portfolio_v1/src"))
sys.path.insert(0, str(REPO / "research/first78_67_audit_repair_v2/src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

BOOK = REPO / "research/choosin_texas/library/nba_2q_regular_8040_1lot_2026_27/book.json"
FIRST80 = REPO / "ROLLER/roller/research/first80.py"
BOOK_HASH = "4da5fdd3a48d2a5513ab6e9452657a790514fbef389a05d0385cfaba009b8cf6"
FIRST80_HASH = "ba895f677938b8e1a33c2eb5d5a9835e8312a007ad207bcfee25f3f32eecb44f"


def _bar(ts: int, bid: int, low: int | None = None) -> dict:
    return {"ts": ts, "bid": bid * 100, "low": None if low is None else low * 100, "ask": bid * 100, "vol": 100}


def test_cross_without_later_80_and_unproven_first():
    from repair.chronology import scan_close_cross
    from roller.choosin_texas.first78.eligibility import find_entry, scan_variants

    crossed = [_bar(1, 70), _bar(2, 78), _bar(3, 79)]
    found = find_entry(crossed)
    assert found["cross_found"] is True
    assert found["signal_ts"] == 2
    reference = scan_close_cross(crossed)
    active = scan_variants(crossed)
    assert active["variants"][67]["stop_ts"] == reference["stop_ts"]
    assert active["entry"]["signal_ts"] == reference["signal_ts"]
    unproven = find_entry([_bar(1, 80), _bar(2, 70)])
    assert unproven["reason"] == "UNPROVEN_FIRST"
    assert unproven["cross_found"] is False


def test_entry_bar_low_does_not_invent_a_stop():
    from roller.choosin_texas.first78.eligibility import scan_variants

    bars = [_bar(1, 70), _bar(2, 78, low=60), _bar(3, 75)]
    scanned = scan_variants(bars)
    assert scanned["variants"][67]["intrabar_ambiguity"] is True
    assert scanned["variants"][67]["stop_ts"] is None


def test_stop_ladder_and_payoffs():
    from first78.money import fee_charged_cents, fee_raw
    from roller.choosin_texas.first78.eligibility import scan_variants
    from roller.choosin_texas.first78.outcomes import cell_name, gross_threshold_cents

    only_67 = scan_variants([_bar(1, 70), _bar(2, 78), _bar(3, 67)])
    only_65 = scan_variants([_bar(1, 70), _bar(2, 78), _bar(3, 65)])
    all_three = scan_variants([_bar(1, 70), _bar(2, 78), _bar(3, 60)])
    assert only_67["variants"][67]["stop_ts"] == 3
    assert only_67["variants"][65]["stop_ts"] is None
    assert only_67["variants"][60]["stop_ts"] is None
    assert only_65["variants"][67]["stop_ts"] == 3
    assert only_65["variants"][65]["stop_ts"] == 3
    assert only_65["variants"][60]["stop_ts"] is None
    assert all_three["variants"][60]["stop_ts"] == 3
    assert gross_threshold_cents(terminal="yes", stopped=False, stop_cents=67) == 22
    assert gross_threshold_cents(terminal="yes", stopped=True, stop_cents=67) == -11
    assert gross_threshold_cents(terminal="yes", stopped=True, stop_cents=65) == -13
    assert gross_threshold_cents(terminal="yes", stopped=True, stop_cents=60) == -18
    assert gross_threshold_cents(terminal="no", stopped=False, stop_cents=67) == -78
    assert gross_threshold_cents(terminal=None, stopped=False, stop_cents=67) is None
    assert cell_name(terminal="no", stopped=False) == "NO_NO_STOP"
    assert cell_name(terminal=None, stopped=False) == "UNRESOLVED"
    assert fee_charged_cents(fee_raw(1, 78)) == fee_charged_cents(fee_raw(1, 78))


def test_desk_marks_official_stop_and_bins_the_67_clock():
    from roller.choosin_texas.first78.desk import build_desk, clock_bin, period_label

    assert clock_bin(10 * 60) == "12:00-9:01"
    assert clock_bin(9 * 60) == "9:00-6:01"
    assert clock_bin(6 * 60) == "6:00-3:01"
    assert clock_bin(3 * 60) == "3:00-0:00"
    assert clock_bin(0) == "3:00-0:00"
    assert period_label(5) == "OT"
    assert period_label(1) is None
    variants = []
    for stop, yes_clear, yes_stop, no_stop in ((67, 2, 1, 1), (65, 3, 0, 1), (60, 3, 0, 1)):
        cells = {"YES_NO_STOP": yes_clear, "YES_STOP": yes_stop, "NO_NO_STOP": 0, "NO_STOP": no_stop, "UNRESOLVED": 0}
        variants.append(
            {
                "stop_cents": stop,
                "role": "OFFICIAL" if stop == 67 else "COMPARISON",
                "n_entries": 4,
                "cells": cells,
                "gross_ev_per_contract": "1",
                "gross_sum_cents": 4,
                "slices": [
                    {
                        "slice": "Q2",
                        "n": 4,
                        "cells": cells,
                        "gross_ev_per_contract": "1",
                        "gross_sum_cents": 4,
                    }
                ],
            }
        )
    desk = build_desk(
        variants,
        [
            {"slice": "Q2", "stopped": True, "stop_period": 4, "stop_remaining_s": 100},
            {"slice": "Q2", "stopped": True, "stop_period": None, "stop_remaining_s": None},
            {"slice": "Q3", "stopped": False, "stop_period": None, "stop_remaining_s": None},
        ],
    )
    assert [path["key"] for path in desk["universe"]["paths"]] == ["78/67", "78/65", "78/60"]
    assert desk["universe"]["paths"][0]["official"] is True
    assert desk["universe"]["trade"]["S_display"] == "2/4"
    assert desk["universe"]["terminal"]["p_display"] == "3/4"
    q2 = desk["partitions"][0]
    assert q2["cells"]["W_and_not_T67"] == 2
    assert q2["cells"]["L_and_not_T67"] == 0
    clock = desk["clocks"][0]
    assert clock["n_stops"] == 2
    assert clock["unavailable"] == 1
    counted = [row for row in clock["bins"] if row["n"]]
    assert counted == [row for row in clock["bins"] if row["label"] == "Q4 3:00-0:00"]
    assert "700/936" not in str(desk)


def test_shared_entries_and_distinct_admissions():
    from roller.choosin_texas.first78.artifact import load_strategy
    from roller.choosin_texas.first78.portfolio_replay import replay_variant
    from roller.choosin_texas.first78.summarize import assemble

    candidates = [
        {
            "game_id": "A",
            "contract_id": "A-YES",
            "sport": "NBA",
            "slice": "Q2",
            "signal_ts": 1,
            "observed_entry_close_cents": 78,
            "terminal": "yes",
            "settlement_ts": 50,
            "stops": {"67": {"stop_ts": 2, "stop_close_cents": 67, "intrabar_ambiguity": False}, "65": {"stop_ts": None}, "60": {"stop_ts": 40, "stop_close_cents": 60, "intrabar_ambiguity": False}},
        },
        {
            "game_id": "B",
            "contract_id": "B-YES",
            "sport": "NBA",
            "slice": "Q3",
            "signal_ts": 3,
            "observed_entry_close_cents": 79,
            "terminal": "no",
            "settlement_ts": 60,
            "stops": {"67": {"stop_ts": None}, "65": {"stop_ts": None}, "60": {"stop_ts": None}},
        },
    ]
    body = assemble(candidates, strategy=load_strategy(), coverage={"entries": 2}, exclusions={}, run_id="fixture", strategy_sha256="abc")
    counts = [row["n_entries"] for row in body["variants"]]
    assert counts == [2, 2, 2]
    assert body["official_strategy_id"] == "FIRST78_67"
    assert body["variants"][0]["role"] == "OFFICIAL"
    short = replay_variant(
        [
            {"game_id": "A", "contract_id": "A", "signal_ts": 1, "exit_ts": 2, "cell": "YES_STOP", "stopped": True, "terminal": "yes"},
            {"game_id": "B", "contract_id": "B", "signal_ts": 3, "exit_ts": 4, "cell": "NO_NO_STOP", "stopped": False, "terminal": "no"},
        ],
        67,
        cap=1,
    )
    longer = replay_variant(
        [
            {"game_id": "A", "contract_id": "A", "signal_ts": 1, "exit_ts": 100, "cell": "YES_STOP", "stopped": True, "terminal": "yes"},
            {"game_id": "B", "contract_id": "B", "signal_ts": 3, "exit_ts": 4, "cell": "NO_NO_STOP", "stopped": False, "terminal": "no"},
        ],
        60,
        cap=1,
    )
    assert short["admitted"] == 2
    assert longer["admitted"] == 1
    assert "B" not in longer["admitted_game_ids"]


def test_ncaab_boundary_and_unknown_variant():
    from roller.choosin_texas.first78.eligibility import ncaab_bucket
    from roller.choosin_texas.models import ChoosinTexasError
    from roller.choosin_texas.first78.artifact import variant_stop

    assert ncaab_bucket(1, 601) == "H1_1"
    assert ncaab_bucket(1, 600) == "H1_2"
    assert ncaab_bucket(1, 599) == "H1_2"
    assert ncaab_bucket(2, 601) == "H2_1"
    assert ncaab_bucket(2, 600) == "H2_2"
    assert ncaab_bucket(2, 599) == "H2_2"
    assert variant_stop("67") == 67
    try:
        variant_stop("40")
    except ChoosinTexasError as exc:
        assert exc.code == "UNKNOWN_VARIANT"
    else:
        raise AssertionError("stop 40 was accepted")


def test_derived_four_membership_and_page_fields():
    from roller.choosin_texas.first78.desk import present_derived
    from roller.choosin_texas.first78.eligibility import find_entry
    from roller.choosin_texas.first78.membership import load_membership

    rows = load_membership()
    assert len(rows) == 936
    assert len({(row["sport"], row["slice"]) for row in rows}) == 4
    capped = find_entry(
        [
            {"ts": 1, "bid": 7000, "low": 7000, "ask": 7000, "vol": 100},
            {"ts": 2, "bid": 8500, "low": 8500, "ask": 8500, "vol": 100},
        ]
    )
    assert capped["cross_found"] is True
    assert capped["observed_close_cents"] >= 84

    def stop_block(n, yes_clear):
        cells = {"YES_NO_STOP": yes_clear, "YES_STOP": n - yes_clear, "NO_NO_STOP": 0, "NO_STOP": 0, "UNRESOLVED": 0}
        return {
            "pool": {"n": n, "gross_sum_cents": n, "gross_ev_per_contract": "1", "cells": cells, "excluded_cap": 0},
            "slices": {
                name: {"n": n if name == "Q2" else 0, "gross_sum_cents": n if name == "Q2" else 0, "gross_ev_per_contract": "1" if name == "Q2" else None, "cells": cells if name == "Q2" else {key: 0 for key in cells}, "excluded_cap": 0}
                for name in ("Q2", "Q3", "H1_2", "H2_1")
            },
        }

    stops = {str(stop): stop_block(4, 3) for stop in (52, 57, 60, 62, 64, 65, 67, 70, 72, 74, 75, 77)}
    stops["67"]["pool"]["excluded_cap"] = 0
    book = {"rule": "FIRST78", "entry_cents": 78, "gain_cents": 22, "cap_cents": 84, "qualified": 4, "stops": stops}
    other = dict(book)
    other79 = {**other, "rule": "FIRST79", "entry_cents": 79, "gain_cents": 21, "cap_cents": 85}
    other81 = {**other, "rule": "FIRST81", "entry_cents": 81, "gain_cents": 19, "cap_cents": 87}
    desk = present_derived(
        {
            "membership_n": 936,
            "exclusions": {"UNPROVEN_FIRST": 2},
            "books": {"78": book, "79": other79, "81": other81},
            "clock_samples": [],
            "scatter_rows": [
                {"ticker": "A", "stopped": False, "entry_margin": 4, "final_margin": 10, "stop_margin": None},
                {"ticker": "B", "stopped": True, "entry_margin": 2, "final_margin": -3, "stop_margin": 1},
            ],
        }
    )
    assert desk["universe"]["trade"]["key"] == "78/67"
    assert [path["key"] for path in desk["universe"]["paths"]] == ["78/52", "78/57", "78/62", "78/67", "78/72", "78/75", "78/77"]
    assert [path["key"] for path in desk["universe"]["mid_paths"]] == ["78/60", "78/64", "78/70", "78/74"]
    assert desk["universe"]["cap_55_excluded"] == 0
    assert desk["companions"][0]["rule"] == "FIRST79"
    assert desk["companions"][1]["rule"] == "FIRST81"
    assert desk["scatter"]["n_survive"] == 1
    assert desk["scatter"]["n_t67"] == 1
    assert desk["partitions"][0]["cells"]["W_and_not_T67"] == 3
    assert "700/936" not in str(desk)


def test_api_does_not_fall_back_to_first80_and_hashes_hold():
    import terminal_api
    from roller.choosin_texas.first78.api import handle_first78

    body = handle_first78("65")
    assert body["official_strategy_id"] == "FIRST78_67"
    assert body.get("fallback_to_first80") is not True
    if body["status"] == "OBSERVED":
        assert body["population_id"] == "DERIVED_FOUR_FIRST78"
        assert body["official_strategy_id"] == "FIRST78_67"
        assert body["requested_stop_cents"] == 65
        assert str(body["cache_key"]).endswith(":65")
        assert "700/936" not in str(body.get("desk"))
    else:
        assert body["status"] in {"ARTIFACT_UNAVAILABLE", "ARTIFACT_STALE", "POPULATION_MISMATCH"}
        assert body["variants"] == []
    client = TestClient(terminal_api.app)
    http = client.get("/choosin-texas/first78?variant=40")
    assert http.status_code == 400
    assert hashlib.sha256(BOOK.read_bytes()).hexdigest() == BOOK_HASH
    assert hashlib.sha256(FIRST80.read_bytes()).hexdigest() == FIRST80_HASH
