"""Strategy/backtest exposure contract. Distinct from Results economics."""

from pathlib import Path

from roller.exposure_contract import (
    EVENT,
    GAME,
    MULTI_ENTRY_PER_GAME,
    TEAM,
    TICKER,
    UNITS,
    resolve_exposure_contract,
    strategy_default,
)


def test_strategy_default_is_game_max_one():
    d = strategy_default()
    assert d["exposure_unit"] == GAME
    assert d["max_entries_per_game"] == 1
    assert d["max_entries_per_unit"] == 1
    assert d["execution_enforced"] is False
    assert d["enforced_by"] == "results_verify_only"
    assert d["source"] == "strategy_default"


def test_undeclared_result_uses_strategy_default():
    c = resolve_exposure_contract({})
    assert c["exposure_unit"] == GAME
    assert c["max_entries_per_unit"] == 1
    assert c["source"] == "strategy_default"


def test_declared_units_are_all_analyzable():
    assert UNITS == {GAME, MULTI_ENTRY_PER_GAME, TEAM, TICKER, EVENT}
    for unit in UNITS:
        c = resolve_exposure_contract({"exposure_unit": unit})
        assert c["exposure_unit"] == unit
        assert c["source"] == "declared"


def test_declared_max_entries_wins():
    c = resolve_exposure_contract({"exposure_unit": GAME, "max_entries_per_game": 3})
    assert c["exposure_unit"] == GAME
    assert c["max_entries_per_unit"] == 3


def test_results_does_not_own_the_default_string():
    src = (Path(__file__).resolve().parents[1] / "roller" / "exposure_contract.py").read_text(encoding="utf-8")
    assert "EXPOSURE_UNIT = GAME" in src
    assert "MAX_ENTRIES_PER_GAME = 1" in src


def test_strategy_enforced_is_opt_in():
    d = strategy_default()
    assert d["enforcement_mode"] == "results_verify_only"
    assert d["execution_enforced"] is False
    c = resolve_exposure_contract({"exposure_unit": GAME})
    assert c["enforcement_mode"] == "results_verify_only"
