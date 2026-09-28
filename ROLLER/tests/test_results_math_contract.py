from roller.results_math.analyze import analyze_result
from roller.results_math.dependence import cluster_readiness
from roller.results_math.ev_contract import ev_contract, settlement_uses_path_rates
from roller.results_math.hurdle import economic_hurdle


def test_ev_contract_three_objects():
    c = ev_contract()
    objs = c["objects"]
    assert objs["observed_path_ev"]["formula"] == "E[exit_close − entry_close]"
    assert "P(WIN)" in objs["book_price_ev"]["formula"]
    assert "P(YES)" in objs["settlement_ev"]["formula"]
    assert "PATH WIN ≠ SETTLEMENT YES" in c["invariants"]


def test_matching_official_settlement_is_not_path_substitution():
    rows = [
        {
            "hyp_pnl_cents": 10,
            "entry_ts": "2026-01-01T00:00:00Z",
            "path_true": True,
            "terminal_yes": True,
            "internal_game_id": "g1",
        }
    ]
    out = analyze_result(
        rows,
        metrics={
            "path_true": 1,
            "path_available": 1,
            "terminal_yes": 1,
            "terminal_available": 1,
            "terminal_missing": 0,
            "win_exit": 1,
            "loss_exit": 0,
        },
    )
    assert out["settlement_payoff"]["status"] != "UNAVAILABLE"
    assert settlement_uses_path_rates(out["settlement_payoff"], 1, 1) is False
    assert settlement_uses_path_rates({"status": "DERIVED", "source": "path_rates", "denominator": 1, "win_n": 1}, 1, 1) is True


def test_settlement_absent_is_not_path_substitution():
    rows = [
        {"hyp_pnl_cents": 5, "entry_ts": "2026-01-01T00:00:00Z", "path_true": True, "internal_game_id": "g1"},
        {"hyp_pnl_cents": -3, "entry_ts": "2026-01-02T00:00:00Z", "path_true": False, "internal_game_id": "g2"},
    ]
    out = analyze_result(
        rows,
        metrics={"path_true": 1, "path_available": 2, "terminal_available": 0, "terminal_missing": 2},
    )
    assert out["settlement_payoff"]["status"] == "UNAVAILABLE"
    assert settlement_uses_path_rates(out["settlement_payoff"], 1, 2) is False
    assert out["ev_contract"]["objects"]["observed_path_ev"]["formula"]
    assert out["observed_ev"]["ci95"]["t_statistic"] is not None
    assert out["observed_ev"]["significance"]["standard_error"] is not None


def test_capitalized_se_and_hurdle():
    rows = [
        {"hyp_pnl_cents": (i % 5) - 2, "entry_ts": f"2026-01-01T00:00:{i:02d}Z", "internal_game_id": f"g{i}"}
        for i in range(8)
    ]
    class _Q:
        entry_conditions = [type("E", (), {"price_e4": 7000})()]
        path_conditions = []

    out = analyze_result(rows, question=_Q())
    cap = out["capitalization"]["observed"]
    assert cap["se_allocation_dollars"] is not None
    assert cap["ev_ci_dollars"]["lower"] < cap["ev_ci_dollars"]["upper"]
    h = out["economic_hurdle"]
    assert h["break_even_total_cost_cents"] == h["observed_gross_ev_cents"]
    assert h["platform_fees"]["reason"] == "not measured"
    assert h["label"].startswith("MINIMUM ECONOMICALLY VIABLE EDGE")
    assert "not profit" in h["label"]


def test_cluster_coincident_vs_collapsed():
    one_each = cluster_readiness(10, 10, unit="game")
    assert one_each["status"] == "COINCIDENT"
    few = cluster_readiness(1, 10, unit="date")
    assert few["status"] == "UNAVAILABLE"
    collapsed = cluster_readiness(4, 20, unit="game")
    assert collapsed["status"] == "DERIVED"


def test_game_cluster_coincident_when_one_per_game():
    rows = [
        {"hyp_pnl_cents": i, "entry_ts": f"2026-01-01T00:00:{i:02d}Z", "internal_game_id": f"g{i}"}
        for i in range(6)
    ]
    out = analyze_result(rows)
    game = out["uncertainty"]["game_cluster_ci"]
    assert game["status"] == "COINCIDENT"
    date = out["uncertainty"]["date_cluster_ci"]
    assert date["status"] == "UNAVAILABLE"
    assert out["uncertainty"]["observation_ci"]["ci95"]["lower"] <= out["uncertainty"]["observation_ci"]["ci95"]["upper"]


def test_date_cluster_derived_when_dates_repeat():
    rows = []
    for d in range(3):
        for i in range(4):
            rows.append(
                {
                    "hyp_pnl_cents": i - 1,
                    "entry_ts": f"2026-01-0{d + 1}T00:00:{i:02d}Z",
                    "internal_game_id": f"g{d}-{i}",
                }
            )
    out = analyze_result(rows)
    date = out["uncertainty"]["date_cluster_ci"]
    assert date["status"] == "DERIVED"
    assert date["mean"]["lower"] <= date["mean"]["upper"]
