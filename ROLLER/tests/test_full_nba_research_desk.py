"""Phase 20: full NBA research desk acceptance.

Frontend draft → ResearchQuestion → compile → capability → ResearchContext
→ ConditionalBacktest (reference ≡ optimized) → Results contract.

Not FIRST80. Not Confirm & Run CSV. Live warehouse is read-only.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from roller.config import RollerConfig
from roller.warehouse.conditional_backtest import (
    Classification,
    compare_backtest_rows,
    run_conditional_backtest,
    run_plan,
)
from roller.warehouse.entities import (
    Game,
    GameMarketLink,
    LinkStatus,
    MarketObservation,
    ObservationBasis,
    Settlement,
    SettlementResult,
)
from roller.warehouse.frontend_contract import (
    compile_frontend_research,
    execute_frontend_research,
    question_from_draft,
    results_contract,
)
from roller.warehouse.query_context import ResearchContext, get_research_context
from roller.warehouse.research_compiler import compile_research

ROLLER_ROOT = Path(__file__).resolve().parents[1]
CFG = RollerConfig(ROLLER_ROOT)
LIVE = ROLLER_ROOT / "data" / "nba" / "2025_2026" / "derived" / "warehouse"
LIVE_SKIP = not (LIVE / "manifest.json").is_file()
GID = "NBA_20251010_BOS_TOR"
TICKER = "KX-BOS"


def _acceptance_draft(**overrides) -> dict:
    """UI-constructed generic strategy: CROSS 65 / REACH 85 / REACH 40."""
    uni = {
        "sports": ["basketball"],
        "leagues": ["NBA"],
        "seasons": ["2025-26"],
        "markets": ["kalshi"],
        "marketData": ["candles"],
        "dateFrom": "2025-10-10",
        "dateTo": "2025-10-10",
    }
    uni.update(overrides.pop("universe", {}))
    return {
        "universe": uni,
        "entryConditions": overrides.pop(
            "entryConditions",
            [{"id": "e1", "family": "cross", "priceCents": 65}],
        ),
        "exitConditions": overrides.pop(
            "exitConditions",
            [
                {"id": "win", "kind": "path", "family": "reach", "priceCents": 85, "outcome": "win"},
                {"id": "loss", "kind": "path", "family": "reach", "priceCents": 40, "outcome": "loss"},
            ],
        ),
        **overrides,
    }


def _obs(ts: str, close: int) -> MarketObservation:
    return MarketObservation(
        ticker=TICKER,
        basis=ObservationBasis.TRADABLE_YES_BID,
        available_at=ts,
        internal_game_id=GID,
        yes_bid_close=close,
    )


def _fixture_ctx(*, closes=None, obs=None, settlements=None) -> ResearchContext:
    return ResearchContext(
        games=(Game(internal_game_id=GID, sport="NBA", season="2025-2026", league="NBA", game_date="2025-10-10"),),
        links=(
            GameMarketLink(
                status=LinkStatus.LINKED,
                internal_game_id=GID,
                ticker=TICKER,
                identity_rule_version="1.0.0",
            ),
        ),
        observations=obs if obs is not None else tuple(_obs(ts, px) for ts, px in (closes or ())),
        settlements=() if settlements is None else settlements,
        pbp_events=(),
        warehouse_version="phase20-fixture",
    )


@pytest.mark.skipif(LIVE_SKIP, reason="Phase 8 warehouse absent")
def test_full_desk_frontend_question_to_results():
    """Researcher chips → ResearchQuestion → compiler → context → engines → Results."""
    question, errors = question_from_draft(_acceptance_draft())
    assert question is not None
    assert not errors
    assert question.universe.sports == ("NBA",)
    assert question.entry_conditions[0].operation.value == "CROSS"
    assert question.entry_conditions[0].price_e4 == 6500
    assert "FIRST80" not in str(question.to_dict())

    compiled = compile_frontend_research({"question": question.to_dict()})
    assert compiled["status"] == "READY"
    assert compiled["source"] == "warehouse_research"
    assert compiled["observation_basis"] == "TRADABLE_YES_BID"
    assert compiled["pit_field"] == "available_at"
    assert compiled["resolution"] == "1_MINUTE_CANDLE"

    plan = compile_research(question, CFG)
    assert plan.status.value == "READY"
    assert plan.plan_hash == compiled["plan_hash"]

    loaded = get_research_context(question, CFG, plan=plan)
    assert loaded.status.value == "READY"
    assert loaded.context is not None
    assert loaded.context.observations
    assert all(o.basis.value == "TRADABLE_YES_BID" for o in loaded.context.observations)

    executed = execute_frontend_research({"question": question.to_dict()}, include_reference=True)
    assert executed["status"] == "READY"
    assert executed["difference_count"] == 0
    contract = executed["results_contract"]
    assert contract["population"] > 0
    assert contract["population"] == 7
    assert contract["classification"]["WIN"] == 1
    assert contract["classification"]["LOSS"] == 6
    assert contract["statistics"]["W"] == 1
    assert contract["statistics"]["L"] == 6
    assert contract["statistics"]["win_rate"] == pytest.approx(1 / 7)
    assert contract["statistics"]["loss_rate"] == pytest.approx(6 / 7)
    assert contract["statistics"]["rr"] == pytest.approx(0.8)
    assert contract["statistics"]["basis"] == "observed_candle_path"
    assert "fill" in contract["statistics"]["not"]
    assert "live_trading_performance" in contract["statistics"]["not"]
    assert contract["coverage"]["executed_population"] == 7
    assert contract["coverage"]["nominal_universe"]["games"] == 1362
    assert "no_event" in contract["exclusions"]
    assert contract["audit_rows"]
    assert "price" not in contract["audit_rows"][0]
    assert contract["reproducibility"]["result_hash"]
    assert contract["reproducibility"]["plan_hash"] == executed["plan_hash"]
    assert "current_time" not in contract["reproducibility"]


@pytest.mark.skipif(LIVE_SKIP, reason="Phase 8 warehouse absent")
def test_reference_equals_optimized_row_by_row():
    question, _ = question_from_draft(_acceptance_draft())
    ref = run_conditional_backtest(question, CFG, engine_id="reference")
    opt = run_conditional_backtest(question, CFG, engine_id="optimized")
    diffs = compare_backtest_rows(ref, opt)
    assert ref.status.value == "READY"
    assert opt.status.value == "READY"
    assert ref.population == opt.population == 7
    assert ref.result_hash == opt.result_hash
    assert len(diffs) == 0
    for r, o in zip(ref.rows, opt.rows, strict=True):
        assert r.identity() == o.identity()
        assert r.entry_timestamp == o.entry_timestamp
        assert r.entry_value == o.entry_value
        assert r.entry_operation == o.entry_operation
        assert r.win_exit_timestamp == o.win_exit_timestamp
        assert r.win_exit_value == o.win_exit_value
        assert r.loss_exit_timestamp == o.loss_exit_timestamp
        assert r.loss_exit_value == o.loss_exit_value
        assert r.classification == o.classification
        assert r.settlement_status == o.settlement_status
        assert r.settlement_value == o.settlement_value


@pytest.mark.skipif(LIVE_SKIP, reason="Phase 8 warehouse absent")
def test_historical_l2_is_data_required():
    compiled = compile_frontend_research(
        {"draft": _acceptance_draft(universe={"marketData": ["historical_l2"]})}
    )
    assert compiled["status"] == "DATA_REQUIRED"
    assert "HISTORICAL_L2" in compiled["capability"]["missing_data"]
    executed = execute_frontend_research(
        {"draft": _acceptance_draft(universe={"marketData": ["historical_l2"]})}
    )
    assert executed["status"] == "DATA_REQUIRED"
    assert executed["result"] is None
    assert executed["status"] != "ZERO_RESULTS"


@pytest.mark.skipif(LIVE_SKIP, reason="Phase 8 warehouse absent")
def test_historical_tick_is_data_required():
    compiled = compile_frontend_research(
        {"draft": _acceptance_draft(universe={"marketData": ["historical_tick"]})}
    )
    assert compiled["status"] == "DATA_REQUIRED"
    assert "HISTORICAL_TICK" in compiled["capability"]["missing_data"]
    executed = execute_frontend_research(
        {"draft": _acceptance_draft(universe={"marketData": ["historical_tick"]})}
    )
    assert executed["status"] == "DATA_REQUIRED"
    assert executed["status"] != "ZERO_RESULTS"


@pytest.mark.skipif(LIVE_SKIP, reason="Phase 8 warehouse absent")
def test_pbp_candle_pit_is_operation_required():
    compiled = compile_frontend_research(
        {"draft": _acceptance_draft(requested_dimensions=["PBP_MARKET_PIT_ALIGNMENT"])}
    )
    assert compiled["status"] == "OPERATION_REQUIRED"
    assert "PBP_MARKET_PIT_ALIGNMENT" in compiled["capability"]["missing_operations"]
    executed = execute_frontend_research(
        {"draft": _acceptance_draft(requested_dimensions=["PBP_MARKET_PIT_ALIGNMENT"])}
    )
    assert executed["status"] == "OPERATION_REQUIRED"
    assert executed["status"] != "ZERO_RESULTS"
    assert executed["result"] is None


@pytest.mark.skipif(LIVE_SKIP, reason="Phase 8 warehouse absent")
def test_zero_results_is_not_missing_data():
    executed = execute_frontend_research(
        {
            "draft": _acceptance_draft(
                entryConditions=[{"id": "e1", "family": "cross", "priceCents": 63, "period": "Q2"}]
            )
        }
    )
    assert executed["status"] == "ZERO_RESULTS"
    assert executed["results_contract"]["population"] == 0
    assert executed["status"] != "DATA_REQUIRED"
    assert executed["status"] != "OPERATION_REQUIRED"
    assert executed["plan_hash"]


def test_missing_settlement_classification():
    question, errors = question_from_draft(
        _acceptance_draft(
            exitConditions=[{"id": "term", "kind": "terminal", "family": "both"}],
        )
    )
    assert question is not None
    assert "missing_threshold" not in errors
    plan = compile_research(question, CFG)
    out = run_plan(
        plan,
        _fixture_ctx(closes=[("2025-10-10T01:00:00Z", 6000), ("2025-10-10T01:01:00Z", 6500)]),
    )
    assert out.rows[0].classification == Classification.MISSING_SETTLEMENT.value
    dumped = out.rows[0].to_dict()
    assert dumped["settlement_status"] == "MISSING"
    assert "fill_price" not in dumped


def test_invalid_settlement_classification():
    question, _ = question_from_draft(
        _acceptance_draft(
            exitConditions=[{"id": "term", "kind": "terminal", "family": "both"}],
        )
    )
    plan = compile_research(question, CFG)
    out = run_plan(
        plan,
        _fixture_ctx(
            closes=[("2025-10-10T01:00:00Z", 6000), ("2025-10-10T01:01:00Z", 6500)],
            settlements=(Settlement(ticker=TICKER, result=SettlementResult.INVALID),),
        ),
    )
    assert out.rows[0].classification == Classification.INVALID_SETTLEMENT.value
    assert out.rows[0].settlement_status == "INVALID"


def test_same_bar_tie_classification():
    question, _ = question_from_draft(_acceptance_draft())
    plan = compile_research(question, CFG)
    ctx = _fixture_ctx(
        obs=(
            _obs("2025-10-10T01:00:00Z", 6000),
            _obs("2025-10-10T01:01:00Z", 6500),
            _obs("2025-10-10T01:02:00Z", 8500),
            MarketObservation(
                ticker=TICKER,
                basis=ObservationBasis.TRADABLE_YES_BID,
                available_at="2025-10-10T01:02:00Z",
                internal_game_id=GID,
                yes_bid_close=4000,
            ),
        )
    )
    out = run_plan(plan, ctx)
    assert out.rows[0].classification == Classification.SAME_BAR_TIE.value
    assert out.rows[0].win_exit_timestamp == out.rows[0].loss_exit_timestamp == "2025-10-10T01:02:00Z"


def test_bounce_exit_compile_execute_fixture():
    """Post-entry Bounce 80¢ WIN on 79→80→79 after a First Touch 80."""
    question, errors = question_from_draft(
        _acceptance_draft(
            entryConditions=[{"id": "e1", "family": "first_touch", "priceCents": 80}],
            exitConditions=[
                {"id": "win", "kind": "path", "family": "bounce", "priceCents": 80, "outcome": "win"},
                {"id": "loss", "kind": "path", "family": "drop_to", "priceCents": 40, "outcome": "loss"},
            ],
        )
    )
    assert question is not None
    assert not errors
    compiled = compile_frontend_research({"question": question.to_dict()})
    assert compiled["status"] == "READY"
    plan = compile_research(question, CFG)
    assert plan.status.value == "READY"
    assert any(x.op == "BOUNCE" for x in plan.exits)
    out = run_plan(
        plan,
        _fixture_ctx(
            closes=[
                ("2025-10-10T01:00:00Z", 7900),
                ("2025-10-10T01:01:00Z", 8000),
                ("2025-10-10T01:02:00Z", 7900),
                ("2025-10-10T01:03:00Z", 8000),
                ("2025-10-10T01:04:00Z", 7900),
            ]
        ),
    )
    assert out.population == 1
    assert out.rows[0].classification == Classification.WIN.value
    assert out.rows[0].win_exit_operation == "BOUNCE"
    assert out.rows[0].win_exit_value == 7900


def test_jump_through_remains_candle_path_not_fill():
    question, _ = question_from_draft(_acceptance_draft())
    plan = compile_research(question, CFG)
    out = run_plan(
        plan,
        _fixture_ctx(
            closes=[
                ("2025-10-10T01:00:00Z", 6000),
                ("2025-10-10T01:01:00Z", 6500),
                ("2025-10-10T01:02:00Z", 3200),
            ]
        ),
    )
    assert out.rows[0].classification == Classification.LOSS.value
    assert out.rows[0].loss_exit_value == 3200
    dumped = out.rows[0].to_dict()
    assert dumped["observation_basis"] == "TRADABLE_YES_BID"
    assert "fill_price" not in dumped
    assert "maker_fill" not in dumped
    assert "fill" not in dumped
    contract = results_contract(question, plan, out)
    assert contract["statistics"]["basis"] == "observed_candle_path"
    assert "fill" in contract["statistics"]["not"]


@pytest.mark.skipif(LIVE_SKIP, reason="Phase 8 warehouse absent")
def test_no_csv_fallback_or_first80_primitive(monkeypatch):
    def _boom(*_a, **_k):
        raise AssertionError("warehouse desk touched CSV / FIRST80")

    monkeypatch.setattr("roller.admin.load_dataset", _boom)
    question, _ = question_from_draft(_acceptance_draft())
    executed = execute_frontend_research({"question": question.to_dict()}, include_reference=True)
    assert executed["source"] == "warehouse_research"
    assert executed["difference_count"] == 0
    text = Path(__file__).resolve().parents[1] / "roller" / "warehouse" / "frontend_contract.py"
    src = text.read_text(encoding="utf-8")
    for token in ("FIRST80", "FIRST75", "FIRST01", "T40", "Lebronner", "PADE"):
        assert token not in src
    tree = ast.parse(src)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert "roller.research_query.execute" not in imported
    assert "roller.research_query.compiler" not in imported
    assert "roller.admin" not in imported
