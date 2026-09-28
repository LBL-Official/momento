#!/usr/bin/env python3
"""STEP 11–12 — Portfolio MC, governors, posterior, non-stationarity.

SCENARIO ANALYSIS. NOT A PERFORMANCE FORECAST.
"""

from __future__ import annotations

from datetime import date

import numpy as np

from common import (
    DIR_PORT,
    FROZEN_N,
    FROZEN_P,
    N_MC,
    OUT,
    PRIOR_P,
    SEED,
    SIGNAL_CAPACITY,
    beta_ci95,
    beta_mean,
    beta_median,
    beta_sf,
    ensure_dirs,
    load_frozen_ledger,
    prior_ab,
    provenance,
    write_json,
    write_parquet,
)
from economics import payoff

BANKROLL0 = 10_000.0
P_BE_GROSS = 2.0 / 3.0


def _governor1_scale(dd: np.ndarray) -> np.ndarray:
    scale = np.ones_like(dd)
    scale = np.where(dd >= 0.05, 0.75, scale)
    scale = np.where(dd >= 0.10, 0.50, scale)
    scale = np.where(dd >= 0.15, 0.25, scale)
    scale = np.where(dd >= 0.20, 0.0, scale)
    return scale


def _week_key(d: str) -> str:
    y, m, day = (int(x) for x in d.split("-"))
    iso = date(y, m, day).isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _month_key(d: str) -> str:
    return d[:7]


def _blocks(outcomes: np.ndarray, keys: list[str]) -> list[np.ndarray]:
    groups: dict[str, list[int]] = {}
    for i, k in enumerate(keys):
        groups.setdefault(k, []).append(int(outcomes[i]))
    return [np.asarray(v, dtype=np.int8) for v in groups.values()]


def _resample_blocks(blocks: list[np.ndarray], n: int, rng: np.random.Generator) -> np.ndarray:
    out = np.empty(n, dtype=np.int8)
    i = 0
    while i < n:
        blk = blocks[int(rng.integers(0, len(blocks)))]
        take = min(len(blk), n - i)
        out[i : i + take] = blk[:take]
        i += take
    return out


def _beta_sf_vec(x: float, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    try:
        from scipy.stats import beta as beta_dist

        return np.asarray(beta_dist.sf(x, a, b), dtype=np.float64)
    except Exception:
        mu = a / (a + b)
        var = a * b / (((a + b) ** 2) * (a + b + 1.0))
        sd = np.sqrt(np.maximum(var, 1e-18))
        z = (x - mu) / sd
        return 0.5 * np.erfc(z / np.sqrt(2.0))


def simulate(
    rng: np.random.Generator,
    n_sims: int,
    outcomes: np.ndarray | None,
    p_survive: float,
    p_fill: float,
    alpha: float,
    f0: float,
    r_win: float,
    r_lose: float,
    governor: str,
    p_be_net: float,
    attempt_rate: float,
    n_trades: int | None = None,
) -> dict:
    n = int(n_trades) if n_trades is not None else FROZEN_N
    eq = np.full(n_sims, BANKROLL0, dtype=np.float64)
    peak = eq.copy()
    max_dd = np.zeros(n_sims)
    under = np.zeros(n_sims)
    recov = np.zeros(n_sims)
    last_dd_start = np.full(n_sims, -1)
    a0, b0 = prior_ab()
    a = np.full(n_sims, a0)
    b = np.full(n_sims, b0)
    two_d = outcomes is not None and getattr(outcomes, "ndim", 1) == 2
    n_steps = n if outcomes is None or not two_d else outcomes.shape[1]
    if outcomes is not None and not two_d:
        n_steps = int(len(outcomes))

    for t in range(n_steps):
        filled = (rng.random(n_sims) < attempt_rate) & (rng.random(n_sims) < p_fill)
        if outcomes is None:
            survive = rng.random(n_sims) < p_survive
        elif two_d:
            survive = outcomes[:, t].astype(bool)
        else:
            survive = np.full(n_sims, bool(outcomes[t]))
        r_t = np.where(survive, r_win, r_lose) * alpha
        r_t = np.where(filled, r_t, 0.0)
        dd = np.clip(1.0 - eq / np.maximum(peak, 1e-12), 0.0, 1.0)
        if governor == "G0":
            f = f0
        elif governor == "G1":
            f = f0 * _governor1_scale(dd)
        else:
            f = f0 * _beta_sf_vec(p_be_net, a, b)
        eq = eq * (1.0 + f * r_t)
        peak = np.maximum(peak, eq)
        dd2 = 1.0 - eq / np.maximum(peak, 1e-12)
        max_dd = np.maximum(max_dd, dd2)
        is_under = eq < peak - 1e-12
        under += is_under.astype(np.float64)
        started = is_under & (last_dd_start < 0)
        last_dd_start = np.where(started, t, last_dd_start)
        recovered = (~is_under) & (last_dd_start >= 0)
        recov = np.where(recovered, recov + (t - last_dd_start), recov)
        last_dd_start = np.where(recovered, -1, last_dd_start)
        if governor == "G2":
            a = a + (filled & survive).astype(np.float64)
            b = b + (filled & ~survive).astype(np.float64)

    term = eq / BANKROLL0
    lo = float(np.percentile(term, 1))
    hi = float(np.percentile(term, 99))
    if hi <= lo:
        hi = lo + 1e-6
    hist, edges = np.histogram(np.clip(term, lo, hi), bins=24, range=(lo, hi))
    return {
        "n_sims": n_sims,
        "n_signals": n_steps,
        "median_equity_multiple": float(np.median(term)),
        "p5_equity_multiple": float(np.percentile(term, 5)),
        "p95_equity_multiple": float(np.percentile(term, 95)),
        "mean_equity_multiple": float(np.mean(term)),
        "p_dd_5": float(np.mean(max_dd >= 0.05)),
        "p_dd_10": float(np.mean(max_dd >= 0.10)),
        "p_dd_20": float(np.mean(max_dd >= 0.20)),
        "p_dd_30": float(np.mean(max_dd >= 0.30)),
        "median_max_dd": float(np.median(max_dd)),
        "p95_max_dd": float(np.percentile(max_dd, 95)),
        "mean_frac_underwater": float(np.mean(under / max(n_steps, 1))),
        "mean_recovery_steps": float(np.mean(recov)),
        "hist_multiples": hist.tolist(),
        "hist_edges": edges.tolist(),
    }


def cusum(x: np.ndarray, mu0: float, k: float = 0.05, h: float = 4.0) -> dict:
    """One-sided CUSUM on failures (looking for a drop in survival)."""
    s = 0.0
    s_max = 0.0
    alarm_t = None
    path = []
    # increment when we see a failure beyond expected
    for i, xi in enumerate(x):
        # score: failure contributes +(1-mu0), survival -(mu0) wait:
        # use (mu0 - xi) so failures (xi=0) push CUSUM up
        s = max(0.0, s + (mu0 - float(xi) - k))
        path.append(s)
        if s > s_max:
            s_max = s
        if alarm_t is None and s >= h:
            alarm_t = i
    return {
        "s_max": s_max,
        "alarm_index": alarm_t,
        "threshold_h": h,
        "allowance_k": k,
        "status": "CUSUM_ALARM" if alarm_t is not None else "NO_ALARM",
    }


def rolling_rate(x: np.ndarray, w: int) -> list[float]:
    out = []
    for i in range(len(x)):
        if i + 1 < w:
            out.append(float("nan"))
        else:
            out.append(float(x[i + 1 - w : i + 1].mean()))
    return out


def main() -> int:
    ensure_dirs()
    rng = np.random.default_rng(SEED)
    ledger = load_frozen_ledger()
    hist = np.array([1 if r.get("winner_or_stop") == "WIN" else 0 for r in ledger], dtype=np.int8)
    dates = [str(r.get("game_date")) for r in ledger]
    week_blocks = _blocks(hist, [_week_key(d) for d in dates])
    month_blocks = _blocks(hist, [_month_key(d) for d in dates])

    a0, b0 = prior_ab()
    a_hist, b_hist = a0 + int(hist.sum()), b0 + int(len(hist) - hist.sum())
    p_be_pub = payoff(40, "PUBLISHED_SCHEDULE_ESTIMATE").p_be or P_BE_GROSS

    posterior = {
        **provenance(),
        "prior_p": PRIOR_P,
        "prior_alpha": a0,
        "prior_beta": b0,
        "prior_mean": beta_mean(a0, b0),
        "prior_median": beta_median(a0, b0),
        "prior_ci95": list(beta_ci95(a0, b0)),
        "P_p_gt_p_be_gross_prior": beta_sf(P_BE_GROSS, a0, b0),
        "P_p_gt_p_be_published_prior": beta_sf(p_be_pub, a0, b0),
        "historical_update_status": "ESTIMATED_CANDLE_PATH_NOT_LIVE_FILLS",
        "hist_survivors": int(hist.sum()),
        "hist_failures": int(len(hist) - hist.sum()),
        "posterior_alpha": a_hist,
        "posterior_beta": b_hist,
        "posterior_mean": beta_mean(a_hist, b_hist),
        "posterior_median": beta_median(a_hist, b_hist),
        "posterior_ci95": list(beta_ci95(a_hist, b_hist)),
        "P_p_gt_p_be_gross_hist": beta_sf(P_BE_GROSS, a_hist, b_hist),
        "P_p_gt_p_be_published_hist": beta_sf(p_be_pub, a_hist, b_hist),
        "live_observations": 0,
        "live_posterior_equals_prior": True,
        "note": "Historical update uses candle-path labels, not observed fills.",
    }

    last25 = hist[-25:]
    last50 = hist[-50:]
    last100 = hist[-100:]
    a25, b25 = a0 + int(last25.sum()), b0 + int(len(last25) - last25.sum())
    cs = cusum(hist.astype(float), mu0=FROZEN_P, k=0.04, h=6.0)
    # Beta-binomial predictive: P(as many failures as last 25 | historical posterior)
    fail25 = int(len(last25) - last25.sum())
    # Monte Carlo predictive from historical posterior
    pred = rng.beta(a_hist, b_hist, size=20_000)
    pred_fail = rng.binomial(25, pred)
    p_tail = float(np.mean(pred_fail >= fail25))
    change = {
        **provenance(),
        "rolling": {
            "last_25": float(last25.mean()),
            "last_50": float(last50.mean()),
            "last_100": float(last100.mean()),
            "full": float(hist.mean()),
        },
        "recent_posterior_mean_25": beta_mean(a25, b25),
        "recent_P_p_gt_p_be_25": beta_sf(P_BE_GROSS, a25, b25),
        "cusum": cs,
        "beta_binomial_p_tail_last25_failures": p_tail,
        "change_detection_status": (
            "STATISTICALLY_MEANINGFUL_REGIME_CHANGE_CANDIDATE"
            if (cs["status"] == "CUSUM_ALARM" and p_tail < 0.01)
            else "NORMAL_VARIANCE"
        ),
        "do_not_declare_edge_decay_from_short_streak": True,
        "label": "CANDLE_PATH_MONITOR_NOT_LIVE_FILLS",
    }

    pay0 = payoff(40, "ZERO_FEE_MODEL")
    pay_pub = payoff(40, "PUBLISHED_SCHEDULE_ESTIMATE")
    pay_st = payoff(40, "CUSTOM_STRESS_MODEL")
    pay35 = payoff(35, "PUBLISHED_SCHEDULE_ESTIMATE")

    def r_pair(pay):
        # Return on allocated cash at 80¢. Loser must be negative.
        return pay.w_cents / 80.0, -pay.l_abs_cents / 80.0

    scenarios = [
        ("A_iid_path_f5_zero", None, FROZEN_P, 1.0, 1.0, 0.05, pay0, "G0", 1.0),
        ("A_iid_path_f5_published", None, FROZEN_P, 1.0, 1.0, 0.05, pay_pub, "G0", 1.0),
        ("A_iid_path_f5_stress", None, FROZEN_P, 1.0, 1.0, 0.05, pay_st, "G0", 1.0),
        ("A_iid_prior725_f5_pub", None, PRIOR_P, 1.0, 1.0, 0.05, pay_pub, "G0", 1.0),
        ("A_iid_p70_f5_pub", None, 0.70, 1.0, 1.0, 0.05, pay_pub, "G0", 1.0),
        ("A_iid_p68_f5_pub", None, 0.68, 1.0, 1.0, 0.05, pay_pub, "G0", 1.0),
        ("A_iid_p67_f5_pub", None, 0.67, 1.0, 1.0, 0.05, pay_pub, "G0", 1.0),
        ("A_iid_p66_f5_pub", None, 0.66, 1.0, 1.0, 0.05, pay_pub, "G0", 1.0),
        ("A_iid_p65_f5_pub", None, 0.65, 1.0, 1.0, 0.05, pay_pub, "G0", 1.0),
        ("A_iid_fill70_f5_pub", None, FROZEN_P, 0.70, 1.0, 0.05, pay_pub, "G0", 1.0),
        ("A_iid_fill50_f5_pub", None, FROZEN_P, 0.50, 1.0, 0.05, pay_pub, "G0", 1.0),
        ("A_iid_stop35_f5_pub", None, FROZEN_P, 1.0, 1.0, 0.05, pay35, "G0", 1.0),
        ("A_iid_f1_pub", None, FROZEN_P, 1.0, 1.0, 0.01, pay_pub, "G0", 1.0),
        ("A_iid_f2_pub", None, FROZEN_P, 1.0, 1.0, 0.02, pay_pub, "G0", 1.0),
        ("A_iid_f3_pub", None, FROZEN_P, 1.0, 1.0, 0.03, pay_pub, "G0", 1.0),
        ("A_iid_gov1_f5_pub", None, FROZEN_P, 1.0, 1.0, 0.05, pay_pub, "G1", 1.0),
        (
            "A_iid_cap1_fill70_f5",
            None,
            FROZEN_P,
            0.70,
            1.0,
            0.05,
            pay_pub,
            "G0",
            SIGNAL_CAPACITY["cap_1"]["accepted"] / FROZEN_N,
        ),
    ]

    rows = []
    featured = {}
    for name, outcomes, p, pf, alpha, f, pay, gov, att in scenarios:
        rw, rl = r_pair(pay)
        stats = simulate(rng, N_MC, outcomes, p, pf, alpha, f, rw, rl, gov, pay.p_be or P_BE_GROSS, att)
        row = {
            **provenance(),
            "scenario": name,
            "method": "A_IID_BERNOULLI",
            "horizon": "SEASON_1230_SIGNALS_SEQUENTIAL",
            "label": "SCENARIO_ANALYSIS_NOT_A_FORECAST",
            "p_survive": p,
            "p_fill": pf,
            "alpha": alpha,
            "f_alloc": f,
            "governor": gov,
            "attempt_rate": att,
            "fee_model_id": pay.fee_model_id,
            "w_cents": pay.w_cents,
            "l_abs_cents": pay.l_abs_cents,
            **{k: v for k, v in stats.items() if k not in ("hist_multiples", "hist_edges")},
        }
        rows.append(row)
        if name in (
            "A_iid_path_f5_published",
            "A_iid_p65_f5_pub",
            "A_iid_fill70_f5_pub",
            "A_iid_gov1_f5_pub",
        ):
            featured[name] = {**row, "hist_multiples": stats["hist_multiples"], "hist_edges": stats["hist_edges"]}
        print(f"  MC {name} median={stats['median_equity_multiple']:.3f} p20dd={stats['p_dd_20']:.3f}", flush=True)

    # Method B — per-simulation weekly / monthly block bootstrap of the candle path
    for label, blocks in (("B_weekly_blocks_f5_pub", week_blocks), ("B_monthly_blocks_f5_pub", month_blocks)):
        boot = np.empty((N_MC, FROZEN_N), dtype=np.int8)
        for i in range(N_MC):
            boot[i] = _resample_blocks(blocks, FROZEN_N, rng)
        rw, rl = r_pair(pay_pub)
        stats = simulate(rng, N_MC, boot, FROZEN_P, 1.0, 1.0, 0.05, rw, rl, "G0", p_be_pub, 1.0)
        rows.append(
            {
                **provenance(),
                "scenario": label,
                "method": "B_BLOCK_BOOTSTRAP",
                "horizon": "SEASON_1230_SIGNALS_SEQUENTIAL",
                "label": "SCENARIO_ANALYSIS_NOT_A_FORECAST",
                "p_survive": float(boot.mean()),
                "p_fill": 1.0,
                "f_alloc": 0.05,
                "governor": "G0",
                "fee_model_id": pay_pub.fee_model_id,
                **{k: v for k, v in stats.items() if k not in ("hist_multiples", "hist_edges")},
            }
        )
        featured[label] = {**rows[-1], "hist_multiples": stats["hist_multiples"], "hist_edges": stats["hist_edges"]}
        print(f"  MC {label} median={stats['median_equity_multiple']:.3f}", flush=True)

    # Governor 2 is sequential Beta per path — 10k paths, labeled as such
    rw, rl = r_pair(pay_pub)
    stats_g2 = simulate(
        rng, 10_000, None, FROZEN_P, 1.0, 1.0, 0.05, rw, rl, "G2", p_be_pub, 1.0
    )
    rows.append(
        {
            **provenance(),
            "scenario": "C_gov2_posterior_sizing_10k",
            "method": "C_REGIME_AND_POSTERIOR",
            "horizon": "SEASON_1230_SIGNALS_SEQUENTIAL",
            "label": "SCENARIO_ANALYSIS_NOT_A_FORECAST",
            "n_sims_note": "10000 (G2 is sequential; not 100k)",
            "p_survive": FROZEN_P,
            "f_alloc": 0.05,
            "governor": "G2",
            **{k: v for k, v in stats_g2.items() if k not in ("hist_multiples", "hist_edges")},
        }
    )

    # Weekly horizon (8 sequential opportunities). Used on the dashboard so a
    # 1,230-trade compound is not the only pictured object.
    for name, p, pf in (
        ("W_iid_8_path_f5_pub", FROZEN_P, 1.0),
        ("W_iid_8_fill70_f5_pub", FROZEN_P, 0.70),
        ("W_iid_8_p65_f5_pub", 0.65, 1.0),
    ):
        stats = simulate(
            rng, N_MC, None, p, pf, 1.0, 0.05, *r_pair(pay_pub), "G0", p_be_pub, 1.0, n_trades=8
        )
        row = {
            **provenance(),
            "scenario": name,
            "method": "A_IID_BERNOULLI",
            "horizon": "8_TRADES_WEEKLY_SLICE",
            "label": "SCENARIO_ANALYSIS_NOT_A_FORECAST",
            "p_survive": p,
            "p_fill": pf,
            "f_alloc": 0.05,
            "governor": "G0",
            "fee_model_id": pay_pub.fee_model_id,
            **{k: v for k, v in stats.items() if k not in ("hist_multiples", "hist_edges")},
        }
        rows.append(row)
        featured[name] = {
            **row,
            "hist_multiples": stats["hist_multiples"],
            "hist_edges": stats["hist_edges"],
        }
        print(f"  MC {name} median={stats['median_equity_multiple']:.4f} p20dd={stats['p_dd_20']:.3f}", flush=True)

    write_parquet(DIR_PORT / "portfolio_simulation.parquet", rows)
    write_parquet(OUT / "portfolio_simulation.parquet", rows)
    write_json(DIR_PORT / "posterior_edge.json", posterior)
    write_json(DIR_PORT / "nonstationarity.json", change)
    write_json(
        DIR_PORT / "summary.json",
        {
            **provenance(),
            "n_mc": N_MC,
            "label": "SCENARIO_ANALYSIS_NOT_A_FORECAST",
            "is_forecast": False,
            "n_scenarios": len(rows),
            "featured": featured,
            "posterior": posterior,
            "nonstationarity": change,
            "concurrent_positions_modeled": False,
            "overlap_is_signal_capacity_only": True,
        },
    )
    print(f"portfolio scenarios={len(rows)} MC={N_MC} change={change['change_detection_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
