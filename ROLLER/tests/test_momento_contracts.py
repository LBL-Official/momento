"""Inter-system contracts. PIT required. Execution disabled."""

from __future__ import annotations

from fractions import Fraction

import pytest

from roller.momento.contracts import LIVE_EXECUTION, MarketState, TradeSignal
from roller.momento.execution import HOOKS, NBA_BOT_ID, SUBMITS, dry_run_intent
from roller.momento.position_management import target_from_research
from roller.momento.relative_value import TkRelativeValueV1, binary_yes_no
from roller.momento.contracts import HedgeAnalysis


STAMP = "2026-09-18T08:00:00+00:00"
AS_OF = "2026-09-18T07:59:00+00:00"


def test_live_execution_false_and_hooks_disabled():
    assert LIVE_EXECUTION is False
    assert SUBMITS is False
    assert NBA_BOT_ID == "nba-first80-001"
    assert HOOKS["enabled"] is False
    assert HOOKS["kill_switch"] is True


def test_pit_rejects_future_as_of():
    with pytest.raises(ValueError, match="PIT"):
        MarketState(
            generated_at=AS_OF,
            as_of=STAMP,
            source_system="database",
            yes_bid_cents=80,
        )


def test_contract_roundtrip_and_rv_components():
    signal = TradeSignal(
        generated_at=STAMP,
        as_of=AS_OF,
        source_system="signal_generation",
        game_id="g1",
        eligible=True,
        reason="research",
    )
    dumped = signal.model_dump()
    assert dumped["schema_version"] == "momento_contract_v1"
    assert TradeSignal.model_validate(dumped).eligible is True
    rv = binary_yes_no(
        TkRelativeValueV1(),
        generated_at=STAMP,
        as_of=AS_OF,
        game_id="g1",
        yes_cents=80,
        no_cents=20,
        yes_anchor_cents=80,
        no_anchor_cents=20,
        beta=Fraction(1, 1),
    )
    assert rv.method == "tk_relative_value_v1"
    assert rv.binary_formula_is_truth is False
    assert rv.relationship_multiplier_denom != 0
    hedge = HedgeAnalysis(
        generated_at=STAMP,
        as_of=AS_OF,
        source_system="hedging_analysis",
        method="test",
        target_exposure_bps=8500,
        note="research",
    )
    target = target_from_research(
        hedge,
        rv,
        current_exposure_bps=10_000,
        generated_at=STAMP,
        as_of=AS_OF,
        game_id="g1",
    )
    assert target.current_exposure_bps == 10_000
    assert target.target_exposure_bps == 8500
    intent = dry_run_intent(target)
    assert intent.submits is False
    assert intent.bot_id == "nba-first80-001"
    assert intent.status == "NOT_IMPLEMENTED"
