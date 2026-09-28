"""Strategy exposure enforcement v1. Results remains verification-only."""

from __future__ import annotations

from pathlib import Path

from roller.exposure_contract import (
    ENFORCEMENT_VERSION,
    EVENT,
    GAME,
    MODE_STRATEGY_ENFORCED,
    MODE_VERIFY_ONLY,
    MULTI_ENTRY_PER_GAME,
    POLICY_FIRST_CHRONO,
    REASON_AMBIGUOUS,
    REASON_DATA_REQUIRED,
    REASON_MAX_EXCEEDED,
    STATUS_AMBIGUOUS,
    STATUS_DATA_REQUIRED,
    STATUS_VALID,
    TEAM,
    TICKER,
    enforce_exposure,
    executable_strategy_contract,
    exposure_identity_payload,
    unit_key,
)
from roller.research_query.compiler import compile_question
from roller.research_query.execute import execute_compiled, execute_question
from roller.research_query.hashing import layer_hashes
from roller.research_query.models import PathCondition, PathOp, TouchOrdinal
from roller.results_math.models import CARDINALITY_VIOLATION
from roller.results_math.results_contract import build_results_contract, results_contract
from tests.mlb_golden import GOLDEN_DRAFT, load_golden
from tests.fixtures.results_contract.envelopes import mlb_last_trade_1661
from tests.test_research_query_engine import _q, _series, _snap_quarter

CONTRACT = Path(__file__).resolve().parents[1] / "roller" / "exposure_contract.py"


def _cand(game, ts, ticker, **extra):
    row = {
        "internal_game_id": game,
        "entry_ts": ts,
        "ticker": ticker,
        "candidate_id": extra.pop("candidate_id", f"{ts}|{ticker}|{game or ''}"),
    }
    row.update(extra)
    return row


def _game1(**kw):
    return executable_strategy_contract(
        exposure_unit=kw.get("exposure_unit", GAME),
        max_entries_per_unit=kw.get("max_entries_per_unit", 1),
        enforcement_mode=kw.get("enforcement_mode", MODE_STRATEGY_ENFORCED),
    )


def _assert_ledger(decision):
    raw = decision["raw_entry_candidates"]
    assert raw == decision["exposure_retained"] + decision["exposure_excluded"]
    assert decision["exposure_eligible"] + decision["exposure_data_required"] == raw
    assert decision["unique_units_after"] <= decision["unique_units_before"] or decision["exposure_data_required"]
    if decision["exposure_unit"] == GAME and decision["max_entries_per_unit"] == 1:
        assert decision["invariants"]["retained_le_unique_units"] is True
        if decision["status"] != STATUS_DATA_REQUIRED:
            assert decision["max_entries_observed"] <= 1


def test_one_game_one_candidate_retained():
    d = enforce_exposure([_cand("A", "2025-12-20T10:01:00Z", "X")], _game1())
    assert d["status"] == STATUS_VALID
    assert [r["ticker"] for r in d["retained"]] == ["X"]
    assert d["exposure_retained"] == 1
    assert d["unique_games_after_exposure"] == 1
    _assert_ledger(d)


def test_one_game_two_chronological_earliest_retained():
    d = enforce_exposure(
        [
            _cand("A", "2025-12-20T10:04:00Z", "Y"),
            _cand("A", "2025-12-20T10:01:00Z", "X"),
        ],
        _game1(),
    )
    assert [r["ticker"] for r in d["retained"]] == ["X"]
    assert d["excluded"][0]["ticker"] == "Y"
    assert d["excluded"][0]["reason"] == REASON_MAX_EXCEEDED
    _assert_ledger(d)


def test_one_game_three_candidates_exactly_one_retained():
    d = enforce_exposure(
        [
            _cand("A", "2025-12-20T10:03:00Z", "Z"),
            _cand("A", "2025-12-20T10:01:00Z", "X"),
            _cand("A", "2025-12-20T10:02:00Z", "Y"),
        ],
        _game1(),
    )
    assert d["exposure_retained"] == 1
    assert d["retained"][0]["ticker"] == "X"
    assert d["max_entries_observed"] == 1
    _assert_ledger(d)


def test_same_timestamp_two_candidates_ambiguous():
    d = enforce_exposure(
        [
            _cand("C", "2025-12-20T10:03:00Z", "Q"),
            _cand("C", "2025-12-20T10:03:00Z", "R"),
        ],
        _game1(),
    )
    assert d["status"] == STATUS_AMBIGUOUS
    assert d["retained"] == []
    assert d["exposure_ambiguous"] == 1
    assert {e["ticker"] for e in d["excluded"]} == {"Q", "R"}
    assert {e["reason"] for e in d["excluded"]} == {REASON_AMBIGUOUS}
    _assert_ledger(d)


def test_spec_example_retain_x_z_ambiguous_c():
    d = enforce_exposure(
        [
            _cand("A", "2025-12-20T10:01:00Z", "X"),
            _cand("A", "2025-12-20T10:04:00Z", "Y"),
            _cand("B", "2025-12-20T10:02:00Z", "Z"),
            _cand("C", "2025-12-20T10:03:00Z", "Q"),
            _cand("C", "2025-12-20T10:03:00Z", "R"),
        ],
        _game1(),
    )
    assert {r["ticker"] for r in d["retained"]} == {"X", "Z"}
    assert d["exposure_retained"] == 2
    reasons = {(e["ticker"], e["reason"]) for e in d["excluded"]}
    assert ("Y", REASON_MAX_EXCEEDED) in reasons
    assert ("Q", REASON_AMBIGUOUS) in reasons
    assert ("R", REASON_AMBIGUOUS) in reasons
    assert d["status"] == STATUS_AMBIGUOUS
    assert d["exposure_ambiguous"] == 1
    _assert_ledger(d)


def test_same_game_different_tickers_group_by_internal_game_id():
    d = enforce_exposure(
        [
            _cand("GAME-1", "2025-12-20T10:01:00Z", "KXMLB-HOME"),
            _cand("GAME-1", "2025-12-20T10:05:00Z", "KXMLB-AWAY"),
        ],
        _game1(),
    )
    assert d["unique_units_before"] == 1
    assert d["exposure_retained"] == 1
    assert d["retained"][0]["ticker"] == "KXMLB-HOME"
    _assert_ledger(d)


def test_different_games_same_timestamp_both_retained():
    d = enforce_exposure(
        [
            _cand("A", "2025-12-20T10:01:00Z", "X"),
            _cand("B", "2025-12-20T10:01:00Z", "Z"),
        ],
        _game1(),
    )
    assert {r["ticker"] for r in d["retained"]} == {"X", "Z"}
    assert d["status"] == STATUS_VALID
    _assert_ledger(d)


def test_missing_internal_game_id_data_required():
    d = enforce_exposure(
        [_cand(None, "2025-12-20T10:01:00Z", "X", internal_game_id=None, game_id=None)],
        _game1(),
    )
    assert d["status"] == STATUS_DATA_REQUIRED
    assert d["retained"] == []
    assert d["excluded"][0]["reason"] == REASON_DATA_REQUIRED
    assert unit_key({"ticker": "X", "entry_ts": "2025-12-20T10:01:00Z"}, GAME) is None
    _assert_ledger(d)


def test_game_max_one_cardinality():
    d = enforce_exposure(
        [
            _cand("A", "2025-12-20T10:01:00Z", "X"),
            _cand("A", "2025-12-20T10:02:00Z", "Y"),
            _cand("B", "2025-12-20T10:01:00Z", "Z"),
        ],
        _game1(),
    )
    assert d["max_entries_observed"] <= 1
    assert d["invariants"]["max_entries_respected"] is True
    games = [r["internal_game_id"] for r in d["retained"]]
    assert len(games) == len(set(games))
    _assert_ledger(d)


def test_multi_entry_per_game_permits_multiple_rows():
    d = enforce_exposure(
        [
            _cand("A", "2025-12-20T10:01:00Z", "X"),
            _cand("A", "2025-12-20T10:04:00Z", "Y"),
        ],
        _game1(exposure_unit=MULTI_ENTRY_PER_GAME, max_entries_per_unit=None),
    )
    assert {r["ticker"] for r in d["retained"]} == {"X", "Y"}
    assert d["status"] == STATUS_VALID
    assert d["max_entries_observed"] == 2


def test_ticker_unit_keeps_tickers_independent():
    d = enforce_exposure(
        [
            _cand("A", "2025-12-20T10:01:00Z", "X"),
            _cand("A", "2025-12-20T10:01:00Z", "Y"),
        ],
        _game1(exposure_unit=TICKER),
    )
    assert {r["ticker"] for r in d["retained"]} == {"X", "Y"}
    assert d["unique_units_after"] == 2


def test_team_and_event_missing_ids_data_required():
    team = enforce_exposure([_cand("A", "2025-12-20T10:01:00Z", "X")], _game1(exposure_unit=TEAM))
    event = enforce_exposure([_cand("A", "2025-12-20T10:01:00Z", "X")], _game1(exposure_unit=EVENT))
    assert team["status"] == STATUS_DATA_REQUIRED
    assert event["status"] == STATUS_DATA_REQUIRED
    ok = enforce_exposure(
        [_cand("A", "2025-12-20T10:01:00Z", "X", team_id="NYY")],
        _game1(exposure_unit=TEAM),
    )
    assert ok["status"] == STATUS_VALID
    assert ok["retained"][0]["ticker"] == "X"


def test_no_home_away_price_volume_te_or_alpha_tie_break():
    src = CONTRACT.read_text(encoding="utf-8")
    body = src.split("def enforce_exposure", 1)[1].split("def _ledger", 1)[0]
    for token in (
        "home",
        "away",
        "favorite",
        "volume",
        "yes_bid",
        "te_score",
        "point_differential",
        "sorted(tickers)",
    ):
        assert token not in body
    d = enforce_exposure(
        [
            _cand(
                "A",
                "2025-12-20T10:01:00Z",
                "ZZZ",
                home="NYY",
                away="BOS",
                entry_close=9000,
                volume=999,
                te_score=12,
            ),
            _cand(
                "A",
                "2025-12-20T10:01:00Z",
                "AAA",
                home="BOS",
                away="NYY",
                entry_close=1000,
                volume=1,
                te_score=0,
            ),
        ],
        _game1(),
    )
    assert d["status"] == STATUS_AMBIGUOUS
    assert d["retained"] == []


def test_file_order_does_not_tie_break_same_timestamp():
    left = enforce_exposure(
        [_cand("A", "2025-12-20T10:01:00Z", "Q"), _cand("A", "2025-12-20T10:01:00Z", "R")],
        _game1(),
    )
    right = enforce_exposure(
        [_cand("A", "2025-12-20T10:01:00Z", "R"), _cand("A", "2025-12-20T10:01:00Z", "Q")],
        _game1(),
    )
    assert left["retained"] == []
    assert right["retained"] == []
    assert left["status"] == right["status"] == STATUS_AMBIGUOUS


def test_clean_population_one_row_per_game():
    d = enforce_exposure(
        [
            _cand("A", "2025-12-20T10:01:00Z", "X"),
            _cand("B", "2025-12-20T10:02:00Z", "Z"),
        ],
        _game1(),
    )
    assert d["invariants"]["clean_retained_eq_units"] is True
    assert d["exposure_retained"] == d["unique_games_after_exposure"] == 2


def test_exposure_version_changes_query_hash():
    q = _q(TouchOrdinal.FIRST_TOUCH, 8000, "Q3")
    bare = layer_hashes(q)
    payload = exposure_identity_payload(executable_strategy_contract())
    enforced = layer_hashes(q, exposure=payload)
    assert bare["question_hash"] != enforced["question_hash"]
    assert "exposure_hash" in enforced
    assert "exposure_hash" not in bare
    bumped = dict(payload)
    bumped["exposure_enforcement_version"] = "9.9.9"
    assert layer_hashes(q, exposure=bumped)["question_hash"] != enforced["question_hash"]
    verify_payload = exposure_identity_payload(
        executable_strategy_contract(enforcement_mode=MODE_VERIFY_ONLY)
    )
    assert verify_payload is None
    assert layer_hashes(q, exposure=verify_payload)["question_hash"] == bare["question_hash"]


def test_results_never_collapses_n():
    rows = [
        {"ticker": "X", "internal_game_id": "A", "path_true": False, "terminal_yes": None},
        {"ticker": "Y", "internal_game_id": "A", "path_true": True, "terminal_yes": None},
    ]
    contract = build_results_contract(
        rows=rows,
        n=2,
        observation_basis="TRADABLE_YES_BID",
    )
    assert contract["rates"]["counts"]["n"] == 2
    assert contract["exposure"]["status"] == CARDINALITY_VIOLATION
    assert contract["exposure"]["n_population"] == 2


def _run(monkeypatch, tickers, **exec_kw):
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    q = _q(
        TouchOrdinal.FIRST_TOUCH,
        7500,
        None,
        path=(PathCondition(id="p", op=PathOp.REACH, price_e4=4000),),
    )
    compiled = compile_question(q)
    assert compiled.reference_match is None
    assert compiled.execution_path.value == "generic_query"
    return execute_compiled(
        compiled,
        ticker_payloads=tickers,
        snap_fn=_snap_quarter("Q3"),
        markets_by_ticker={t: {"result": "yes"} for t in tickers},
        **exec_kw,
    )


def test_verify_only_mode_unchanged(monkeypatch):
    tickers = {
        "X": _series([7000, 8000, 8100], ticker="X", game="A"),
        "Y": _series([7000, 7000, 7000, 7000, 8000], ticker="Y", game="A"),
    }
    out = _run(monkeypatch, tickers)
    assert out["execution_status"] == "COMPLETE"
    assert out.get("exposure") is None
    ids = {r["ticker"] for r in out["population"]["trades"]}
    assert ids == {"X", "Y"}
    assert out["summary"]["population_n"] == 2
    assert not any(s.get("condition_id") == "exposure" for s in out["population"]["funnel"])
    assert out["hashes"].get("exposure_hash") is None


def test_enforcement_before_path_and_results(monkeypatch):
    tickers = {
        "X": _series([7000, 8000, 8100], ticker="X", game="A"),
        "Y": _series([7000, 7000, 7000, 7000, 8000, 4000], ticker="Y", game="A"),
    }
    verify = _run(monkeypatch, tickers)
    assert {r["ticker"] for r in verify["population"]["trades"]} == {"X", "Y"}
    y = next(r for r in verify["population"]["trades"] if r["ticker"] == "Y")
    assert y["path_true"] is True
    out = _run(
        monkeypatch,
        tickers,
        exposure_enforcement_mode=MODE_STRATEGY_ENFORCED,
        exposure_unit=GAME,
        max_entries_per_unit=1,
    )
    assert out["execution_status"] == "COMPLETE"
    trades = out["population"]["trades"]
    assert [r["ticker"] for r in trades] == ["X"]
    assert trades[0]["path_true"] is not True
    funnel_ids = [s.get("condition_id") for s in out["population"]["funnel"]]
    assert "exposure" in funnel_ids
    assert funnel_ids.index("exposure") < len(funnel_ids)
    stages = [s["stage"] for s in out["stages"]]
    assert stages.index("period_filter") < stages.index("path")
    n = out["summary"]["population_n"]
    assert n == 1
    results_n = ((out.get("analysis") or {}).get("results_contract") or {}).get("rates", {}).get("counts", {}).get("n")
    assert results_n == 1
    exp = out["exposure"]
    assert exp["enforcement_mode"] == MODE_STRATEGY_ENFORCED
    assert exp["selection_policy"] == POLICY_FIRST_CHRONO
    assert exp["exposure_enforcement_version"] == ENFORCEMENT_VERSION
    assert exp["raw_entry_candidates"] == 2
    assert exp["exposure_retained"] == 1
    assert exp["exposure_excluded"] == 1
    _assert_ledger(exp)


def test_strategy_enforced_one_row_per_game(monkeypatch):
    tickers = {
        "X": _series([7000, 8000], ticker="X", game="A"),
        "Y": _series([7000, 7000, 7000, 8000], ticker="Y", game="A"),
        "Z": _series([7000, 8000], ticker="Z", game="B"),
    }
    out = _run(
        monkeypatch,
        tickers,
        exposure_enforcement_mode=MODE_STRATEGY_ENFORCED,
    )
    trades = out["population"]["trades"]
    games = [r["internal_game_id"] for r in trades]
    assert len(games) == len(set(games))
    assert set(games) == {"A", "B"}
    assert out["summary"]["population_n"] == 2
    assert out["exposure"]["max_entries_observed"] <= 1


def test_strategy_enforced_missing_game_id_fails_closed(monkeypatch):
    tickers = {"X": _series([7000, 8000], ticker="X", game="")}
    out = _run(
        monkeypatch,
        tickers,
        exposure_enforcement_mode=MODE_STRATEGY_ENFORCED,
    )
    assert out["execution_status"] == "DATA_REQUIRED"
    assert out["summary"]["population_n"] is None
    assert out["exposure"]["exposure_status"] == STATUS_DATA_REQUIRED
    assert out["population"]["status"] == "ABSENT"


def test_multi_entry_execute_permits_two_rows(monkeypatch):
    tickers = {
        "X": _series([7000, 8000], ticker="X", game="A"),
        "Y": _series([7000, 7000, 7000, 8000], ticker="Y", game="A"),
    }
    out = _run(
        monkeypatch,
        tickers,
        exposure_enforcement_mode=MODE_STRATEGY_ENFORCED,
        exposure_unit=MULTI_ENTRY_PER_GAME,
        max_entries_per_unit=None,
    )
    assert {r["ticker"] for r in out["population"]["trades"]} == {"X", "Y"}


def test_ticker_execute_keeps_sides_independent(monkeypatch):
    tickers = {
        "X": _series([7000, 8000], ticker="X", game="A"),
        "Y": _series([7000, 7000, 7000, 8000], ticker="Y", game="A"),
    }
    out = _run(
        monkeypatch,
        tickers,
        exposure_enforcement_mode=MODE_STRATEGY_ENFORCED,
        exposure_unit=TICKER,
    )
    assert {r["ticker"] for r in out["population"]["trades"]} == {"X", "Y"}


def test_execute_question_reads_draft_mode(monkeypatch):
    monkeypatch.setattr("roller.research_query.availability._dataset_exists", lambda *a, **k: True)
    draft = {
        "universe": {
            "sports": ["basketball"],
            "leagues": ["NBA"],
            "seasons": ["2025-26"],
            "markets": ["kalshi"],
            "marketData": ["candles"],
        },
        "entryConditions": [{"id": "e1", "family": "first_touch", "priceCents": 75}],
        "exitConditions": [{"id": "t", "kind": "terminal", "family": "both"}],
        "exposureEnforcementMode": "strategy_enforced",
        "exposureUnit": "GAME",
        "maxEntriesPerGame": 1,
    }
    out = execute_question(
        {"draft": draft},
        ticker_payloads={
            "X": _series([7000, 8000], ticker="X", game="A"),
            "Y": _series([7000, 7000, 7000, 8000], ticker="Y", game="A"),
        },
        snap_fn=_snap_quarter("Q3"),
    )
    assert out["exposure"]["enforcement_mode"] == MODE_STRATEGY_ENFORCED
    assert out["summary"]["population_n"] == 1


def test_existing_mlb_554_object_unchanged():
    golden = load_golden()
    draft = GOLDEN_DRAFT
    assert not draft.get("exposure_enforcement_mode")
    assert not draft.get("exposureEnforcementMode")
    assert not draft.get("exposure_enforcement")
    assert golden["expected"]["n"] == 554
    assert golden["expected"]["question_hash"] == (
        "aaef0cbd185379f060a17077957ad50ee9cd2b4b25c339f1f3c1b25695060449"
    )
    from roller.research_query.compiler import compile_draft

    compiled = compile_draft(draft)
    hashes = layer_hashes(compiled.question, state=draft["teFilters"])
    assert hashes["question_hash"] == golden["expected"]["question_hash"]
    assert "exposure_hash" not in hashes


def test_existing_mlb_1661_object_unchanged():
    env = mlb_last_trade_1661()
    assert env["summary"]["population_n"] == 1661
    assert env.get("exposure") is None
    contract = results_contract(env)
    assert contract["rates"]["counts"]["n"] == 1661
    assert contract["exposure"]["execution_enforced"] is False
    assert contract["exposure"]["enforced_by"] == MODE_VERIFY_ONLY
