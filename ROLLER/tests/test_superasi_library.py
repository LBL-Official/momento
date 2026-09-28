"""SuperASI disk library. Not localStorage."""

from __future__ import annotations

from roller.superasi.library import list_packages, load_package, write_decomp, write_package
from roller.superasi.package import new_package


def _trade():
    return {
        "ticker": "T-A",
        "internal_game_id": "G-A",
        "sport": "NBA",
        "slice": "Q3",
        "entry_close": 80,
        "path_true": True,
        "win_exit": True,
        "loss_exit": False,
        "terminal_yes": True,
        "price_basis": "YES_BID_CLOSE",
    }


def test_atomic_roundtrip(tmp_path):
    pkg, trades = new_package(source="roller_generic", trades=[_trade()])
    write_package(pkg, trades, [], root=tmp_path)
    loaded = load_package(pkg["package_id"], root=tmp_path)
    assert loaded["package"]["population_n"] == 1
    assert loaded["trades"][0]["ticker"] == "T-A"
    write_decomp(pkg["package_id"], {"ok": True}, root=tmp_path)
    listed = list_packages(root=tmp_path)
    assert listed[0]["decomposition_status"] == "PRESENT"
    assert listed[0]["source"] == "roller_generic"
    assert "name" in listed[0]
    assert "workflow_draft" in listed[0]
