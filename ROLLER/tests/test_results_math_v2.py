"""Deterministic Results Math v2. Path WIN is never settlement YES."""

from __future__ import annotations

from roller.results_math.analyze import analyze_result
from roller.results_math.bootstrap import bootstrap_returns
from roller.results_math.dependence import cluster_readiness
from roller.results_math.ev_contract import settlement_uses_path_rates
from roller.results_math.formatting import MINUS, format_drawdown_dollars, format_signed_dollars
from roller.results_math.means import mean, sample_std, sample_variance, t_interval
from roller.results_math.models import NOT_COMPUTED, UNAVAILABLE
from roller.results_math.observations import normalize_rows, valid_returns
from roller.results_math.path_metrics import (
    downside_deviation,
    expected_shortfall,
    observed_path_sharpe,
    payoff_ratio,
    profit_factor,
    sortino_ratio,
)
from roller.results_math.payoff import (
    binary_entry_continuum,
    binary_entry_sensitivity,
    book_payoffs,
    breakeven_probability,
    decompose,
    ev_from_probability,
    payoff_ev,
    transform_rate_interval_to_ev,
)
from roller.results_math.proportions import clopper_pearson, wilson_interval
from roller.results_math.sizing import size_allocation
from roller.results_math.versions import BOOTSTRAP_SEED, CODE_VERSION, SCHEMA_VERSION, SEMANTICS_VERSION


def _q(entry=7000, win=8500, loss=3500):
    class _Q:
        entry_conditions = [type("E", (), {"price_e4": entry})()]
        path_conditions = [
            type("P", (), {"outcome": type("O", (), {"value": "win"})(), "op": type("Op", (), {"value": "REACH"})(), "price_e4": win})(),
            type("P", (), {"outcome": type("O", (), {"value": "loss"})(), "op": type("Op", (), {"value": "DROP_TO"})(), "price_e4": loss})(),
        ]

    return _Q()


def _rows_84_113(*, extra=None):
    rows = []
    for i in range(84):
        rows.append(
            {
                "hyp_pnl_cents": 2 if i < 45 else 1,
                "entry_ts": f"2026-01-01T00:{i:02d}:00Z",
                "entry_close": 7000,
                "exit_close": 7200,
                "exit_outcome": "WIN_EXIT",
                "path_true": True,
                "internal_game_id": f"g{i}",
                "ticker": f"T{i}",
            }
        )
    for i in range(29):
        rows.append(
            {
                "hyp_pnl_cents": -3 if i < 15 else -2,
                "entry_ts": f"2026-01-02T00:{i:02d}:00Z",
                "entry_close": 7000,
                "exit_close": 6700,
                "exit_outcome": "LOSS_EXIT",
                "path_true": False,
                "internal_game_id": f"gL{i}",
                "ticker": f"L{i}",
            }
        )
    if extra:
        rows.extend(extra)
    return rows


def test_versions_are_2_0_0():
    assert SEMANTICS_VERSION == "2.0.0"
    assert SCHEMA_VERSION == "2.0.0"
    assert CODE_VERSION == "results_math_v2.0.0"
    out = analyze_result(_rows_84_113()[:2], question=_q())
    assert out["results_math_semantics_version"] == "2.0.0"
    assert out["observed_path"]["status"] == "OBSERVED"


def test_mean_variance_std():
    xs = [1.0, 2.0, 3.0, 4.0]
    assert mean(xs) == 2.5
    assert abs(sample_variance(xs) - (5.0 / 3.0)) < 1e-12
    assert abs(sample_std(xs) - (5.0 / 3.0) ** 0.5) < 1e-12


def test_student_t_ci_and_pvalue():
    xs = [2.0, -1.0, 3.0, 0.0, 1.0]
    ci = t_interval(xs)
    assert ci is not None
    assert ci["df"] == 4
    assert ci["t_statistic"] == ci["estimate"] / ci["standard_error"]
    assert ci["lower"] < ci["estimate"] < ci["upper"]
    assert 0.0 <= ci["p_value"] <= 1.0
    assert ci["zero_inside_ci"] is True


def test_wilson_and_transformed_book_ev_84_113():
    w = wilson_interval(84, 113)
    assert abs(w["p_hat"] - 84 / 113) < 1e-15
    assert abs(w["lower"] - 0.6557613200313875) < 1e-12
    assert abs(w["upper"] - 0.8149620050205827) < 1e-12
    ev_ci = transform_rate_interval_to_ev(w, 15, -35)
    assert abs(ev_ci["lower"] + 2.2119339984306237) < 1e-12
    assert abs(ev_ci["upper"] - 5.748100251029136) < 1e-12
    assert ev_ci["zero_inside_ci"] is True


def test_clopper_pearson_transformed_ev():
    cp = clopper_pearson(84, 113)
    ev_ci = transform_rate_interval_to_ev(cp, 15, -35)
    assert ev_ci["lower"] < 0 < ev_ci["upper"]
    assert ev_ci["method"] == "clopper_pearson_transformed_ev"


def test_book_ev_and_breakeven():
    ev = ev_from_probability(84 / 113, 15, -35)
    assert abs(ev - (84 * 15 + 29 * (-35)) / 113) < 1e-12
    assert abs(ev - 2.1681415929203567) < 1e-12
    assert breakeven_probability(15, -35) == 0.7
    book = decompose(win_n=84, loss_n=29, win_payoff_cents=15, loss_payoff_cents=-35)
    assert abs(book["ev_cents"] - ev) < 1e-12
    assert book["wilson_ev_ci"]["zero_inside_ci"] is True
    assert "p_ev_gt_zero" not in book


def test_binary_100_0_and_entry_continuum():
    s = binary_entry_sensitivity(84 / 113)
    by = {r["entry_cents"]: r for r in s["rows"]}
    assert abs(by[70]["payoff_ev_cents"] - (100 * 84 / 113 - 70)) < 1e-12
    cont = binary_entry_continuum(84 / 113)
    assert abs(cont["breakeven_entry_cents"] - 100 * 84 / 113) < 1e-12
    rows = {r["entry_cents"]: r["payoff_ev_cents"] for r in cont["rows"]}
    assert abs(rows[70] - rows[71] - 1.0) < 1e-12
    assert rows[70] > 0
    assert rows[75] < 0


def test_allocation_1428_and_capitalized():
    s = size_allocation(allocation_cents=100_000, entry_cents=70)
    assert s["contracts"] == 1428
    assert s["deployed_cents"] == 99960
    assert s["residual_cents"] == 40
    ev = ev_from_probability(84 / 113, 15, -35)
    assert abs(ev * 1428 / 100 - 30.961061946902692) < 1e-9
    assert abs((89 * 1428) / 113 / 100 - 11.2470796460177) < 1e-9


def test_sharpe_sortino_profit_factor_payoff_ratio_es():
    xs = [5.0, -2.0, 4.0, -1.0, 0.0]
    assert abs(observed_path_sharpe(xs) - (mean(xs) / sample_std(xs))) < 1e-12
    assert sortino_ratio(xs) == mean(xs) / downside_deviation(xs)
    pf = profit_factor(xs)
    assert pf["status"] == "DERIVED"
    assert abs(pf["value"] - 9.0 / 3.0) < 1e-12
    pr = payoff_ratio(xs)
    assert pr["status"] == "DERIVED"
    es = expected_shortfall(xs, 0.05, min_tail=1)
    assert es["status"] == "OBSERVED"
    assert es["mean_cents"] <= 0


def test_quantiles_and_drawdown_sign():
    xs = list(range(-2, 8))
    from roller.results_math.means import quantiles

    q = quantiles(xs)
    assert q["p5"] <= q["p50"] <= q["p95"]
    assert format_drawdown_dollars(2156.28) == "$2,156.28"
    assert MINUS in format_signed_dollars(-599.76)
    assert format_signed_dollars(-599.76).startswith(MINUS + "$")
    assert format_signed_dollars(11.25).startswith("+$")


def test_no_p_ev_gt_zero_and_no_ror():
    out = analyze_result(_rows_84_113(), question=_q(), metrics={"win_exit": 84, "loss_exit": 29, "path_true": 84, "path_available": 113, "terminal_available": 0, "terminal_missing": 113})
    assert out["observed_ev"]["significance"]["p_ev_gt_zero"]["status"] == NOT_COMPUTED
    assert out["risk_of_ruin"]["status"] == NOT_COMPUTED
    assert "P(EV > 0)" not in str(out["diagnostics"]["survivability"]["prose"])
    assert out["settlement"]["status"] == UNAVAILABLE
    assert settlement_uses_path_rates(out["settlement"], 84, 113) is False


def test_snapshot_reconciliation_book_and_path_distinct():
    rows = []
    for i in range(113):
        win = i < 84
        rows.append(
            {
                "hyp_pnl_cents": 2 if win and i < 5 else (1 if win else (-1 if i < 108 else 0)),
                "entry_ts": f"2026-02-01T00:{i:02d}:00Z",
                "entry_close": 7000,
                "exit_outcome": "WIN_EXIT" if win else "LOSS_EXIT",
                "path_true": win,
                "internal_game_id": f"g{i}",
            }
        )
    out = analyze_result(rows, question=_q(), metrics={"win_exit": 84, "loss_exit": 29, "path_true": 84, "path_available": 113, "terminal_available": 0, "terminal_missing": 113})
    book = out["book_price"]
    assert abs(book["ev_cents"] - 2.1681415929203567) < 1e-9
    assert book["wilson_ev_ci"]["zero_inside_ci"] is True
    assert out["observed_ev"]["estimate_cents"] != book["ev_cents"]
    sizing = out["allocation"]["sizing"]
    assert sizing["contracts"] == 1428
    assert sizing["residual_cents"] == 40
    cap_book = out["allocation"]["book"]["expected_allocation_dollars"]
    assert abs(cap_book - 30.961061946902692) < 1e-6
    assert out["settlement"]["status"] == UNAVAILABLE


def test_bootstrap_determinism_and_share_not_probability():
    xs = [1.0, -2.0, 3.0, 0.0, 4.0, -1.0]
    a = bootstrap_returns(xs, iterations=200, seed=BOOTSTRAP_SEED)
    b = bootstrap_returns(xs, iterations=200, seed=BOOTSTRAP_SEED)
    assert a["mean"] == b["mean"]
    assert a["sharpe"] == b["sharpe"]
    assert "NOT P(EV > 0)" in a["share_means_positive_label"]
    assert 0.0 <= a["share_means_positive"] <= 1.0


def test_game_and_date_clustering():
    one = cluster_readiness(113, 113, unit="game")
    assert one["status"] == "COINCIDENT"
    assert "ONE OBSERVATION PER GAME" in one["reason"]
    few = cluster_readiness(1, 10, unit="date")
    assert few["status"] == UNAVAILABLE
    collapsed = cluster_readiness(4, 20, unit="game")
    assert collapsed["status"] == "DERIVED"
    rows = []
    for d in range(3):
        for i in range(4):
            rows.append(
                {
                    "hyp_pnl_cents": i - 1,
                    "entry_ts": f"2026-01-0{d+1}T00:00:{i:02d}Z",
                    "internal_game_id": f"g{d}-{i}",
                }
            )
    out = analyze_result(rows)
    assert out["clusters"]["date"]["status"] == "DERIVED"
    assert out["clusters"]["date"]["mean"]["lower"] <= out["clusters"]["date"]["mean"]["upper"]
    coincident = analyze_result(
        [{"hyp_pnl_cents": i, "entry_ts": f"2026-01-01T00:00:{i:02d}Z", "internal_game_id": f"g{i}"} for i in range(6)]
    )
    assert coincident["clusters"]["game"]["status"] == "COINCIDENT"
    assert coincident["clusters"]["game"]["mean"] is not None


def test_missing_exit_and_missing_payoff():
    rows = [{"entry_ts": "2026-01-01T00:00:00Z", "entry_close": 7000, "internal_game_id": "g1"}]
    out = analyze_result(rows, question=_q())
    assert out["observed_path"]["status"] == UNAVAILABLE
    assert "Need >= 1" in out["observed_path"]["reason"] or "Missing exit" in out["observed_path"]["reason"]
    no_chips = analyze_result(
        [{"hyp_pnl_cents": 1, "entry_ts": "2026-01-01T00:00:00Z", "internal_game_id": "g1"}],
        question=type("Q", (), {"entry_conditions": [type("E", (), {"price_e4": 7000})()], "path_conditions": []})(),
    )
    assert no_chips["book_price"]["status"] == UNAVAILABLE


def test_invalid_payoff_win_le_loss():
    bad = decompose(win_n=10, loss_n=5, win_payoff_cents=-10, loss_payoff_cents=5)
    assert bad["status"] == "INVALID_SEMANTICS"
    w, l = book_payoffs(70, 60, 80)
    assert w <= l


def test_adversarial_n1_zero_variance_all_signs():
    one = analyze_result([{"hyp_pnl_cents": 4, "entry_ts": "2026-01-01T00:00:00Z", "internal_game_id": "g1"}])
    assert one["observed_ev"]["ci95"] is None
    zeros = analyze_result(
        [{"hyp_pnl_cents": 0, "entry_ts": f"2026-01-01T00:00:{i:02d}Z", "internal_game_id": f"g{i}"} for i in range(5)]
    )
    assert zeros["observed_path"]["observed_path_sharpe"] is None
    assert zeros["observed_path"]["sortino"] is None
    pos = profit_factor([1.0, 2.0, 3.0])
    assert pos["status"] == UNAVAILABLE
    two = t_interval([1.0, 1.0])
    assert two["standard_error"] == 0
    assert two["t_statistic"] is None


def test_property_scaling_and_ev_identity():
    xs = [2.0, -3.0, 5.0]
    c = 7.0
    assert abs(mean([c * x for x in xs]) - c * mean(xs)) < 1e-12
    p, w, l = 0.6, 15.0, -35.0
    assert abs(ev_from_probability(p, w, l) - (l + p * (w - l))) < 1e-12
    assert abs(float(payoff_ev(p, w, l)) - ev_from_probability(p, w, l)) < 1e-12
    assert abs(breakeven_probability(w, l) + l / (w - l)) < 1e-12
    assert abs((100 * 0.743) - 70 - (100 * 0.743 - 70)) < 1e-12
    s = size_allocation(allocation_cents=100_000, entry_cents=70)
    assert abs(2.1681415929203567 * s["contracts"] - 2.1681415929203567 * 1428) < 1e-12
    wils = wilson_interval(84, 113)
    ev_ci = transform_rate_interval_to_ev(wils, 15, -35)
    assert ev_ci["lower"] < ev_ci["upper"]
    flipped = transform_rate_interval_to_ev(wils, -35, 15)
    assert flipped["lower"] < flipped["upper"]


def test_no_rounding_before_aggregation_from_e4():
    rows = [
        {"entry_close": 7010, "exit_close": 7140, "entry_ts": "2026-01-01T00:00:00Z", "internal_game_id": "g1"},
        {"entry_close": 7020, "exit_close": 6905, "entry_ts": "2026-01-01T00:00:01Z", "internal_game_id": "g2"},
    ]
    xs = valid_returns(normalize_rows(rows))
    assert xs[0] == (7140 - 7010) / 100.0
    assert xs[1] == (6905 - 7020) / 100.0
    assert abs(mean(xs) - ((7140 - 7010) + (6905 - 7020)) / 200.0) < 1e-12


def test_envelope_objects_and_survivability_prose():
    out = analyze_result(
        _rows_84_113(),
        question=_q(),
        metrics={"win_exit": 84, "loss_exit": 29, "path_true": 84, "path_available": 113, "terminal_available": 0, "terminal_missing": 113},
    )
    for key in ("observed_path", "book_price", "settlement", "allocation", "drawdown", "bootstrap", "clusters", "robustness", "diagnostics"):
        assert key in out
    assert out["diagnostics"]["survivability"]["status"] == "DERIVED"
    assert "quality" not in out["diagnostics"]["survivability"]["label"].lower() or "not a quality" in out["diagnostics"]["survivability"]["label"].lower()
    assert "TRADE QUALITY" not in out["diagnostics"]["survivability"]["prose"]
    assert out["robustness"]["binary_entry_continuum"]["status"] == "HYPOTHETICAL"
    assert out["diagnostics"]["power"]["status"] in ("MODEL_ASSUMED", UNAVAILABLE)
    assert out["allocation"]["book"]["ev_ci_dollars"]["lower"] < out["allocation"]["book"]["ev_ci_dollars"]["upper"]


def test_missing_game_id_and_mixed_settlement():
    rows = [
        {"hyp_pnl_cents": 2, "entry_ts": "2026-01-01T00:00:00Z", "terminal_yes": True, "exit_outcome": "WIN_EXIT"},
        {"hyp_pnl_cents": -1, "entry_ts": "2026-01-01T00:00:01Z", "terminal_yes": None, "exit_outcome": "LOSS_EXIT", "internal_game_id": "g2"},
    ]
    out = analyze_result(
        rows,
        question=_q(),
        metrics={"win_exit": 1, "loss_exit": 1, "terminal_yes": 1, "terminal_available": 1, "terminal_missing": 1, "path_true": 1, "path_available": 2},
    )
    assert out["settlement"]["status"] == "DERIVED"
    assert out["settlement"]["denominator"] == 1
    assert out["clusters"]["game"]["n_units"] >= 1
    frac = size_allocation(allocation_cents=100_000, entry_cents=70)
    assert frac["residual_cents"] == 40
    assert frac["contracts"] * 70 + frac["residual_cents"] == 100_000
