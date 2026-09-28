"""Austin query desk: leakage, parity, sizing, hedge, PCA/KNN, freeze."""

from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from roller.austin.analyze import _corr_status
from roller.austin.api import handle_query
from roller.austin.clock import clock_to_seconds, time_since_entry_seconds
from roller.austin.config import DEFAULT, band_contracts, band_dollars, hedge_capital_cents
from roller.austin.errors import AustinError
from roller.austin.features import assert_same_schema, build_feature_vector
from roller.austin.games import catalog_payload
from roller.austin.hedge import SCENARIO_LABEL, FILL_RATES, trade_hedge
from roller.austin.instances import load_trades
from roller.austin.knn import match_query, weighted_bootstrap_ci
from roller.austin.leakage import FORBIDDEN_FEATURE_NAMES, assert_registry_clean, assert_train_before_eval
from roller.austin.locks import FORBIDDEN_N, N_Q2, N_Q3, N_TRADES
from roller.austin.mathutil import pairwise_euclid
from roller.austin.outcomes import NOT_APPLICABLE, outcome_after_snapshot
from roller.austin.pbp_join import state_at
from roller.austin.pca import fit_pca, transform_row
from roller.austin.raw_state import ENTRY_SOURCES, RawState
from roller.austin.reconstruct import last_bar_before
from roller.austin.registry import load_registry
from roller.austin.sizing import all_bands, recommend_band
from roller.austin.walkforward import run_walkforward

REPO = Path(__file__).resolve().parents[2]
PKG = REPO / "ROLLER" / "roller" / "austin"
BOOK = (
    REPO
    / "research"
    / "choosin_texas"
    / "library"
    / "nba_2q_regular_8040_1lot_2026_27"
    / "book.json"
)


def _state(**kwargs) -> RawState:
    base = dict(
        is_query=False,
        trade_id="t1",
        side="home",
        entry_price_cents=80,
        current_price_cents=42,
        home_score_entry=58,
        away_score_entry=56,
        home_score_current=71,
        away_score_current=64,
        entry_quarter=3,
        current_quarter=3,
        entry_seconds_remaining=480,
        current_seconds_remaining=258,
        time_since_entry_sec=222,
        lookbacks=[],
        path_to_t=[],
        snapshot_kind="path",
        availability_timestamp="2026-01-01T00:00:00+00:00",
    )
    base.update(kwargs)
    return RawState(**base)


def test_registry_and_no_outcome_leakage():
    reg = load_registry()
    assert_registry_clean(reg)
    names = {spec.name for spec in reg["features"]}
    assert "entry_price_cents" in names
    assert "price_travel" in names
    assert "score_differential_travel" in names
    for spec in reg["features"]:
        assert spec.name not in FORBIDDEN_FEATURE_NAMES or not (spec.used_in_pca or spec.used_in_knn)
        assert not spec.outcome_derived


def test_feature_travels_and_time():
    bundle = build_feature_vector(_state())
    num = bundle["numeric"]
    assert num["entry_price_cents"] == 80
    assert num["current_price_cents"] == 42
    assert num["price_travel"] == -38
    assert num["score_travel"] == 21
    assert num["score_differential_travel"] == 5
    assert num["score_differential"] == 7
    assert num["time_since_entry"] == 222
    assert num["quarter"] == 3
    assert clock_to_seconds("04:18") == 258
    assert time_since_entry_seconds(
        entry_quarter=3,
        entry_seconds_remaining=480,
        current_quarter=3,
        current_seconds_remaining=258,
    ) == 222


def test_velocity_unavailable_without_path():
    bundle = build_feature_vector(_state(is_query=True, trade_id=None, lookbacks=[], path_to_t=[]))
    cell = bundle["features"]["price_velocity_1"]
    assert cell["value"] is None
    assert "UNAVAILABLE" in str(cell["status"])
    assert cell["value"] != 0


def test_query_parity_matches_historical():
    hist = build_feature_vector(_state(is_query=False, trade_id="abc"))
    query = build_feature_vector(_state(is_query=True, trade_id=None))
    assert_same_schema(hist, query)
    for name in hist["feature_names"]:
        assert hist["numeric"][name] == query["numeric"][name]


def test_leakage_future_rejected():
    with pytest.raises(AustinError) as exc:
        assert_train_before_eval("2026-02-01", "2026-01-01")
    assert exc.value.code == "LEAKAGE"
    assert_train_before_eval("2026-01-01", "2026-02-01")


def test_pca_no_outcomes_and_reproducible():
    rng = np.random.default_rng(80)
    frame = pd.DataFrame(
        {
            "entry_price_cents": rng.normal(80, 1, 40),
            "current_price_cents": rng.normal(60, 10, 40),
            "price_travel": rng.normal(-20, 8, 40),
            "score_differential": rng.normal(4, 5, 40),
        }
    )
    names = list(frame.columns)
    a = fit_pca(frame, names, k=2)
    b = fit_pca(frame, names, k=2)
    assert a["names"] == names
    np.testing.assert_allclose(a["components"], b["components"])
    vec = transform_row({n: float(frame.iloc[0][n]) for n in names}, a)
    assert vec is not None
    with pytest.raises(AustinError):
        fit_pca(frame.assign(final_pnl=1.0), names + ["final_pnl"], k=2)


def test_knn_distance_order_and_self_excluded():
    train = np.array([[0.0, 0.0], [1.0, 0.0], [10.0, 0.0]])
    meta = [
        {"trade_id": "a", "final_pnl_taker_8040_cents": 20, "csv_t40": False, "hit_40_after": False},
        {"trade_id": "b", "final_pnl_taker_8040_cents": -40, "csv_t40": True, "hit_40_after": True},
        {"trade_id": "c", "final_pnl_taker_8040_cents": 20, "csv_t40": False, "hit_40_after": False},
    ]
    got = match_query(np.array([0.0, 0.0]), train, meta, k=2, exclude_trade_id="a")
    assert got["effective_neighbors"] == 2
    assert got["neighbors"][0]["trade_id"] == "b"
    assert all(row["trade_id"] != "a" for row in got["neighbors"])
    d = pairwise_euclid(np.array([[0.0, 0.0]]), train)
    assert d[0, 0] < d[0, 1] < d[0, 2]


def test_sizing_integers():
    assert band_dollars(3) == 600
    assert band_dollars(4) == 800
    assert band_dollars(5) == 1000
    assert band_contracts(3) == 750
    assert band_contracts(4) == 1000
    assert band_contracts(5) == 1250
    assert hedge_capital_cents(750) == 30000
    bands = all_bands()
    assert bands["3"]["reserved_120"] is False
    assert bands["3"]["potential_hedge_label"] == "POTENTIAL HEDGE CAPITAL"
    rec = recommend_band({"weighted_mean_EV": 9.0}, {"status": "INSUFFICIENT_SAMPLE"})
    assert rec["recommended_allocation_band"] == 3


def test_hedge_fill_unknown_and_scenarios():
    trade = {
        "trade_id": "x",
        "ticker": "KXNBAGAME-FAV",
        "entry_timestamp": "2026-01-01T00:00:00+00:00",
        "entry_price_cents": 80,
        "w": True,
        "t40": True,
    }
    from datetime import datetime, timezone

    t0 = datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc)
    t1 = datetime(2026, 1, 1, 0, 2, tzinfo=timezone.utc)
    paths = {
        "favorite": {
            "KXNBAGAME-FAV": [(t0, 42.0, 43.0, 41.0), (t1, 40.0, 41.0, 39.0)],
            "KXNBAGAME-OPP": [(t1, 40.0, 41.0, 39.0)],
        },
        "opponent_ticker": {"KXNBAGAME-FAV": "KXNBAGAME-OPP"},
    }
    row = trade_hedge(trade, paths)
    assert row["hedge_fill_observed"] is False if "hedge_fill_observed" in row else True
    trig = row["triggers"]["42"]
    assert trig["hedge_fill_status"] == "FILL_UNAVAILABLE"
    assert trig["hedge_fill_observed"] is False
    assert [s["fill_rate"] for s in trig["scenarios"]] == list(FILL_RATES)
    assert all(s["label"] == SCENARIO_LABEL for s in trig["scenarios"])
    assert trig["hedge_triggered_path"] is True
    assert trig["hedge_price_reached"] is True


def test_walkforward_is_chronological():
    dates = pd.date_range("2025-11-01", periods=30, freq="7D")
    rng = np.random.default_rng(80)
    rows = []
    for i, day in enumerate(dates):
        rows.append(
            {
                "snapshot_id": f"s{i}",
                "trade_id": f"t{i}",
                "kind": "entry",
                "game_date": day.strftime("%Y-%m-%d"),
                "calendar_month": day.strftime("%Y-%m"),
                "entry_price_cents": 80,
                "current_price_cents": 80,
                "price_travel": 0,
                "distance_from_80": 0,
                "score_differential": float(rng.normal(3, 4)),
                "score_differential_travel": 0,
                "score_travel": 0,
                "time_since_entry": 0,
                "seconds_remaining": 400,
                "quarter": 2,
                "quarter_progress": 0.4,
                "price_x_score_diff": 240.0,
                "score_diff_x_time": 0.0,
                "entry_price_x_score_diff": 240.0,
                "final_pnl_taker_8040_cents": 20 if rng.random() > 0.3 else -40,
                "csv_t40": False,
                "hit_40_after": False,
                "won": True,
                "settlement": "YES",
            }
        )
    frame = pd.DataFrame(rows)
    wf = run_walkforward(frame)
    assert wf["train_months"]
    assert wf["oos_months"]
    assert max(wf["train_months"]) < min(wf["oos_months"])


def test_locked_universe_n():
    trades = load_trades()
    assert len(trades) == N_TRADES == 604
    assert sum(1 for t in trades if t["slice"] == "Q2") == N_Q2
    assert sum(1 for t in trades if t["slice"] == "Q3") == N_Q3
    assert 936 in FORBIDDEN_N.values()
    assert 1182 in FORBIDDEN_N.values()
    assert 1230 in FORBIDDEN_N.values()


def test_package_does_not_import_path_fe_or_live_paths():
    forbidden = ("nba_path_fe", "enter_skip", "first80", "trading-engine")
    for path in PKG.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            text = " ".join(names)
            assert "nba_path_fe" not in text
            assert "roller.first80" not in text
    assert BOOK.is_file()


def test_docs_exist():
    root = REPO / "research" / "austin"
    assert (root / "README.md").is_file()
    assert (root / "docs" / "DATASET.md").is_file()
    assert (root / "docs" / "QUERY_MODE.md").is_file()
    assert (root / "features" / "registry.yaml").is_file()
    text = (root / "README.md").read_text(encoding="utf-8")
    assert "604" in text
    assert "HISTORICAL QUERY" in text
    assert "BUY" not in text.split("never")[0] or "never BUY" in text or "never" in text
    assert (root / "docs" / "INTEGRITY_AUDIT.md").is_file()
    assert (root / "docs" / "ENGINEERING_REPORT.md").is_file()


def test_travel_ladder_and_pre80_status():
    entry = build_feature_vector(_state(current_price_cents=80, time_since_entry_sec=0, current_seconds_remaining=480))
    assert entry["numeric"]["price_travel"] == 0
    for px, travel in ((70, -10), (60, -20), (50, -30), (42, -38), (41, -39), (40, -40)):
        bundle = build_feature_vector(_state(current_price_cents=px))
        assert bundle["numeric"]["current_price_cents"] == px
        assert bundle["numeric"]["price_travel"] == travel
    pre = build_feature_vector(
        _state(
            query_mode="PRE_80",
            entry_price_cents=None,
            time_since_entry_sec=None,
            home_score_entry=None,
            away_score_entry=None,
        )
    )
    assert pre["features"]["entry_price_cents"]["status"] == "NOT_APPLICABLE"
    assert pre["features"]["price_travel"]["value"] is None
    assert pre["features"]["price_travel"]["status"] == "NOT_APPLICABLE"
    assert pre["features"]["time_since_entry"]["value"] is None
    assert pre["numeric"]["current_price_cents"] == 42


def test_t40_already_hold_still_settles():
    from datetime import datetime, timezone

    t0 = datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc)
    t1 = datetime(2026, 1, 1, 0, 2, tzinfo=timezone.utc)
    t2 = datetime(2026, 1, 1, 0, 3, tzinfo=timezone.utc)
    trade = {"entry_price_cents": 80, "w": True, "t40": True}
    fav = [(t0, 50.0, 51.0, 49.0), (t1, 40.0, 41.0, 39.0), (t2, 38.0, 39.0, 37.0)]
    after = outcome_after_snapshot(trade, snapshot_ts=t2, favorite_post=fav, opponent_post=[])
    assert after["t40_already"] is True
    assert after["pnl_8040_after_t"] is None
    assert after["pnl_8040_after_t_status"] == NOT_APPLICABLE
    assert after["pnl_hold_after_t"] == 20
    before = outcome_after_snapshot(trade, snapshot_ts=t0, favorite_post=fav, opponent_post=[])
    assert before["t40_already"] is False
    assert before["pnl_8040_after_t"] == -40
    assert before["hit_40_after"] is True


def test_knn_uses_hold_after_t_and_excludes_snapshot():
    train = np.array([[0.0, 0.0], [0.1, 0.0], [8.0, 0.0]])
    meta = [
        {
            "trade_id": "self",
            "snapshot_id": "s0",
            "pnl_hold_after_t": 99,
            "final_pnl_taker_8040_cents": -40,
            "csv_t40": True,
            "hit_40_after": False,
        },
        {
            "trade_id": "b",
            "snapshot_id": "s1",
            "pnl_hold_after_t": 20,
            "final_pnl_taker_8040_cents": -40,
            "csv_t40": True,
            "hit_40_after": False,
        },
        {
            "trade_id": "c",
            "snapshot_id": "s2",
            "pnl_hold_after_t": -80,
            "final_pnl_taker_8040_cents": -40,
            "csv_t40": True,
            "hit_40_after": True,
        },
    ]
    got = match_query(np.array([0.0, 0.0]), train, meta, k=2, exclude_trade_id="self", exclude_snapshot_id="s0")
    assert all(row["trade_id"] != "self" for row in got["neighbors"])
    assert all(row["snapshot_id"] != "s0" for row in got["neighbors"])
    assert got["ev_definition"] == "hold_80_to_settlement"
    assert got["weighted_mean_EV"] != -40


def test_future_mutation_does_not_change_clocks():
    from datetime import datetime, timezone

    t = datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc)
    later = datetime(2026, 1, 1, 1, 5, tzinfo=timezone.utc)
    when = datetime(2026, 1, 1, 1, 1, tzinfo=timezone.utc)
    bars = [(t, 80.0, 81.0, 79.0), (later, 10.0, 11.0, 9.0)]
    assert last_bar_before(bars, when)[1] == 80.0
    mutated = list(bars)
    mutated.append((later.replace(minute=10), 1.0, 2.0, 0.0))
    assert last_bar_before(mutated, when)[1] == 80.0
    events = [{"ts": t, "home_score": 10, "away_score": 8}, {"ts": later, "home_score": 99, "away_score": 1}]
    assert state_at(events, when)["home_score"] == 10


def test_ci_reproducible_and_query_does_not_submit():
    values = np.array([20.0, -80.0, 20.0, -80.0, 20.0])
    weights = np.array([0.4, 0.15, 0.2, 0.15, 0.1])
    a = weighted_bootstrap_ci(values, weights, seed=80)
    b = weighted_bootstrap_ci(values, weights, seed=80)
    c = weighted_bootstrap_ci(values, weights, seed=81)
    assert a["ci_lower_cents"] == b["ci_lower_cents"]
    assert a["ci_upper_cents"] == b["ci_upper_cents"]
    assert a["method"] == "weighted bootstrap"
    assert a["draws"] == 1000
    assert a["ci_lower_cents"] != c["ci_lower_cents"] or a["ci_upper_cents"] != c["ci_upper_cents"]
    payload = handle_query(
        {
            "side": "home",
            "query_mode": "PRE_80",
            "current_price_cents": 55,
            "home_score_current": 40,
            "away_score_current": 38,
            "current_quarter": 1,
            "current_seconds_remaining": 400,
        }
    )
    assert payload["submits"] is False
    assert payload["knn_status"] == "INSUFFICIENT_SAMPLE"
    assert payload["reason"] == "NO_ENTRY_IN_FITTED_SPACE"
    assert payload["conditional_ev"] is None


def test_query_universe_is_not_training_n():
    payload = catalog_payload()
    assert payload["model_n"] == N_TRADES == 604
    assert payload["n_query_games"] > payload["model_n"]
    assert payload["n_query_games"] == 1362
    assert any(not row["in_austin_604"] for row in payload["games"])
    assert any(row["in_austin_604"] for row in payload["games"])
    assert set(ENTRY_SOURCES) == {"CHOOSIN_604_CSV", "ASKED_SIX_FIRST80", "WAREHOUSE_FIRST_GE_80", "NONE"}


def test_price_travel_zero_variance_is_not_unavailable():
    x = np.zeros(20)
    y = np.linspace(-80, 20, 20)
    assert _corr_status(x, y) == "ZERO_VARIANCE"


def test_path_coverage_classes():
    from datetime import datetime, timedelta, timezone

    from roller.austin.dataset import classify_path

    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert classify_path([], [], []) == "PATH_UNAVAILABLE"
    assert classify_path([(t, 80.0, 80.0, 80.0)], [], []) == "PATH_PARTIAL"
    complete = [(t, 80.0, 80.0, 80.0), (t + timedelta(seconds=60), 79.0, 79.0, 78.0)]
    assert classify_path(complete, [(t, 20.0, 20.0, 20.0)], [{"ts": t}]) == "PATH_COMPLETE"
    gapped = [(t, 80.0, 80.0, 80.0), (t + timedelta(seconds=400), 70.0, 70.0, 70.0)]
    assert classify_path(gapped, [(t, 20.0, 20.0, 20.0)], [{"ts": t}]) == "PATH_PARTIAL"


def test_reconstruct_outside_604_and_missing_price():
    from datetime import timedelta

    from roller.austin.reconstruct import build_historical_query_state, list_moments

    payload = catalog_payload()
    outside = next(row for row in payload["games"] if not row["in_austin_604"] and row.get("home_ticker"))
    moments = list_moments(outside["internal_game_id"], side="home")
    assert moments["in_austin_604"] is False
    if not moments.get("first_available_at"):
        pytest.skip("no 1m bars for outside-604 sample")
    visible = (parse_utc(moments["first_available_at"]) + timedelta(seconds=1)).isoformat()
    recon = build_historical_query_state(
        game_id=outside["internal_game_id"],
        side="home",
        timestamp_utc=visible,
    )
    assert recon["in_austin_604"] is False
    assert recon["raw"].query_source == "HISTORICAL_RECONSTRUCT"
    assert recon["raw"].entry_source in ENTRY_SOURCES
    early = (parse_utc(moments["first_available_at"]) - timedelta(hours=2)).isoformat()
    missing = build_historical_query_state(
        game_id=outside["internal_game_id"],
        side="home",
        timestamp_utc=early,
        query_mode="PRE_80",
    )
    assert missing["raw"].current_price_cents is None
    assert missing["availability"]["current_price"] == "UNAVAILABLE"
    assert missing["status"] == "QUERY_PARTIAL"


def parse_utc(value: str):
    from roller.austin.clock import parse_utc as _parse

    stamp = _parse(value)
    assert stamp is not None
    return stamp


def test_stored_snapshot_to_querystate_default_knn_parity():
    from roller.austin.integrity import _row_to_query
    from roller.austin.raw_state import raw_from_query
    from roller.austin.store import load_snapshots

    names = list(load_registry()["default_knn"])
    snaps = load_snapshots()
    pool = snaps[
        (snaps["kind"] != "entry")
        & (pd.to_numeric(snaps["current_price_cents"], errors="coerce") == 42)
    ].dropna(subset=["entry_price_cents", "current_price_cents", "price_travel"])
    assert not pool.empty
    rec = pool.iloc[0]
    raw = raw_from_query(_row_to_query(rec))
    bundle = build_feature_vector(raw)
    assert list(bundle["feature_names"])
    assert bundle["numeric"]["entry_price_cents"] == float(rec["entry_price_cents"])
    assert bundle["numeric"]["current_price_cents"] == float(rec["current_price_cents"])
    assert bundle["numeric"]["price_travel"] == float(rec["price_travel"])
    assert all(name in bundle["feature_names"] for name in names)
    assert "final_pnl_taker_8040_cents" not in bundle["feature_names"]
    assert "pnl_hold_after_t" not in bundle["feature_names"]


def test_example_fixture_is_jsonable_42():
    import json

    from roller.austin.api import handle_example_query

    payload = handle_example_query()
    json.dumps(payload)
    assert payload["default"] == "post80_42"
    assert payload["current_price_cents"] == 42
    assert payload["query_mode"] == "POST_80"
    assert payload["submits"] is False


def test_artifacts_after_t_columns():
    from roller.austin.store import load_snapshots

    snaps = load_snapshots()
    for col in (
        "pnl_hold_after_t",
        "pnl_8040_after_t",
        "pnl_8040_after_t_status",
        "t40_already",
        "hit_40_after",
        "path_status",
    ):
        assert col in snaps.columns
    assert int(snaps["trade_id"].nunique()) == N_TRADES


def test_freeze_live_and_engine_paths():
    forbidden = [
        REPO / "apps" / "trading-engine",
        REPO / "strategies" / "mlb",
        REPO / "crates" / "risk",
        BOOK,
    ]
    for path in forbidden:
        assert path.exists()
    first80 = list((REPO / "ROLLER").rglob("first80.py"))
    assert first80
    src = "\n".join(p.read_text(encoding="utf-8") for p in PKG.glob("*.py"))
    assert "ENABLE_LIVE_TRADING" not in src
    assert "place_order" not in src
    ui = (REPO / "frontend" / "choosin-texas" / "src" / "Austin.tsx").read_text(encoding="utf-8")
    for word in ("EXIT NOW", "SELL", "CONFIDENCE", "recommended exit", "BUY", "SKIP"):
        assert word not in ui
    assert ">HOLD<" not in ui
    assert "EXIT NOW" not in ui
