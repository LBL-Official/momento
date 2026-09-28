"""Deterministic decompose + asked-six seed locks."""

from __future__ import annotations

from fractions import Fraction

from roller.superasi.decompose import decompose
from roller.superasi.exit_mixes import ev_from_s
from roller.superasi.four_cell import as_fractions
from roller.superasi.library import load_package
from roller.superasi.seed import SEED_ID, build_seed


def test_path_only_decompose_ev_without_terminal(tmp_path):
    from roller.superasi.library import write_package
    from roller.superasi.package import new_package

    rows = [
        {
            "ticker": "A",
            "internal_game_id": "G1",
            "sport": "NBA",
            "entry_close": 80,
            "path_true": True,
            "win_exit": True,
            "loss_exit": False,
            "price_basis": "YES_BID_CLOSE",
        },
        {
            "ticker": "B",
            "internal_game_id": "G2",
            "sport": "NBA",
            "entry_close": 80,
            "path_true": True,
            "win_exit": True,
            "loss_exit": False,
            "price_basis": "YES_BID_CLOSE",
        },
        {
            "ticker": "C",
            "internal_game_id": "G3",
            "sport": "NBA",
            "entry_close": 80,
            "path_true": False,
            "win_exit": False,
            "loss_exit": True,
            "exit_close": 40,
            "price_basis": "YES_BID_CLOSE",
        },
    ]
    pkg, trades = new_package(source="roller_generic", trades=rows)
    write_package(pkg, trades, [], root=tmp_path)
    out = decompose(pkg["package_id"], fill_algorithm="LEDGER_RULE", persist=False, root=tmp_path)
    assert out["four_cell"]["status"] == "PATH_ONLY"
    assert as_fractions(out["four_cell"])["S"] == Fraction(2, 3)
    assert Fraction(out["active_mix"]["EV"]["numer"], out["active_mix"]["EV"]["denom"]) == 0
    assert out["adverse_terminal"]["status"] == "DATA_REQUIRED"


def test_asked_six_seed_and_mix_switch(tmp_path):
    build_seed(root=tmp_path)
    loaded = load_package(SEED_ID, root=tmp_path)
    assert loaded["package"]["population_n"] == 1182
    assert loaded["package"]["source"] == "seed_asked_six"
    a = decompose(SEED_ID, fill_algorithm="LEDGER_RULE", persist=False, root=tmp_path)
    b = decompose(SEED_ID, fill_algorithm="FIRST_BARRIER_CLOSE", persist=False, root=tmp_path)
    s = as_fractions(a["four_cell"])["S"]
    assert s == Fraction(883, 1182)
    assert a["four_cell"]["cells"] == b["four_cell"]["cells"]
    assert a["active_mix"]["S"] == b["active_mix"]["S"]
    assert a["active_mix"]["EV"] != b["active_mix"]["EV"]
    assert Fraction(a["active_mix"]["EV"]["numer"], a["active_mix"]["EV"]["denom"]) == Fraction(5700, 1182)
    assert Fraction(b["active_mix"]["EV"]["numer"], b["active_mix"]["EV"]["denom"]) == Fraction(4058, 1182)
    assert ev_from_s(s, 20, Fraction(40)) == Fraction(5700, 1182)
    plan = decompose(SEED_ID, fill_algorithm="PLANNING_2_5", persist=False, root=tmp_path)
    assert Fraction(plan["active_mix"]["mean_L"]["numer"], plan["active_mix"]["mean_L"]["denom"]) == Fraction(
        14705, 299
    )
    assert Fraction(plan["active_mix"]["EV"]["numer"], plan["active_mix"]["EV"]["denom"]) == Fraction(5, 2)
