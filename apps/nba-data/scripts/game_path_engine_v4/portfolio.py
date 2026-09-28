#!/usr/bin/env python3
"""Trade economics, policy frontier, Kelly sensitivity, ruin, edge decay.

Research only. Cash map is the documented 80/40 research assumption, not Kalshi fills.
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np

from common import (
    BREAKEVEN_Q,
    MODELS,
    OBS,
    PORT,
    Q_UNCONDITIONAL,
    REP,
    ev_from_q,
    read_parquet_rows,
    utc_now,
    write_json,
    write_parquet,
)

EQUITY0 = 10_000.0
FRAC = 0.02
MAX_CONCURRENT = 5
WIN_CASH = 0.25
LOSS_CASH = 0.50
P_STRESS = (0.74, 0.725, 0.70, 0.68, 0.67, 0.66)


def r_unit(y40):
    return -2.0 if int(y40) else 1.0


def cash_mult(y40):
    return -LOSS_CASH if int(y40) else WIN_CASH


def stats_R(rs):
    rs = np.asarray(rs, dtype=float)
    if len(rs) == 0:
        return {}
    mu = float(rs.mean())
    var = float(rs.var(ddof=1)) if len(rs) > 1 else 0.0
    sd = var ** 0.5
    downside = rs[rs < 0]
    dvar = float((downside ** 2).mean()) if len(downside) else 0.0
    cvar = None
    if len(rs) >= 20:
        q = np.quantile(rs, 0.05)
        tail = rs[rs <= q]
        cvar = float(tail.mean()) if len(tail) else float(q)
    eq = np.cumsum(rs)
    peak = np.maximum.accumulate(eq)
    dd = eq - peak
    return {
        "n": int(len(rs)),
        "mean_R": mu,
        "var_R": var,
        "sharpe_per_trade": None if sd < 1e-12 else mu / sd,
        "sortino_per_trade": None if dvar < 1e-12 else mu / (dvar ** 0.5),
        "cvar_5": cvar,
        "max_dd_R_path": float(dd.min()) if len(dd) else 0.0,
        "acceptance_rate": 1.0,
        "sample_warning": "LOW_SHORT_SAMPLE_NON_IID",
    }


def policy_accept(rows, name, p_cut=None, skip_regimes=None):
    out = []
    for r in rows:
        acc = True
        if name == "hold_all":
            acc = True
        elif name == "skip_high_p" and p_cut is not None:
            acc = r["p_selected"] <= p_cut
        elif name == "skip_fragile_regimes":
            acc = r.get("regime") not in (skip_regimes or ())
        elif name == "half_size_high_p" and p_cut is not None:
            acc = True
        out.append(acc)
    return out


def apply_returns(rows, accept, size_frac):
    rs = []
    cash = []
    for r, ok, f in zip(rows, accept, size_frac):
        if not ok:
            continue
        rs.append(r_unit(r["Y_40_CLOSE"]) * f)
        cash.append(cash_mult(r["Y_40_CLOSE"]) * f)
    return rs, cash


def kelly_curve(p, fs=None):
    fs = fs if fs is not None else np.linspace(0.001, 0.40, 80)
    g = []
    for f in fs:
        if 1.0 - LOSS_CASH * f <= 0:
            g.append((-np.inf, float(f)))
            continue
        val = p * np.log(1.0 + WIN_CASH * f) + (1.0 - p) * np.log(1.0 - LOSS_CASH * f)
        g.append((float(val), float(f)))
    g.sort(reverse=True)
    return g[0][1], g[0][0], [{"f": f, "g": val} for val, f in sorted(g, key=lambda z: z[1])]


def month_blocks(rows):
    by = defaultdict(list)
    for r in rows:
        by[(r.get("game_date") or "")[:7]].append(int(r["Y_40_CLOSE"]))
    return [v for v in by.values() if v]


def ruin_paths(p, n_trades, n_sims, f, rng, block_ys=None, month_blocks_data=None):
    """Equity fraction paths. Barrier probability is 1-p when sampling Bernoulli."""
    hits = {0.80: 0, 0.70: 0, 0.50: 0}
    min_eq = []
    for _ in range(n_sims):
        eq = EQUITY0
        m = eq
        if month_blocks_data:
            seq = []
            while len(seq) < n_trades:
                seq.extend(month_blocks_data[int(rng.integers(0, len(month_blocks_data)))])
            barrier = [bool(x) for x in seq[:n_trades]]
        elif block_ys is None:
            barrier = rng.random(n_trades) < (1.0 - p)
        else:
            idx = rng.integers(0, len(block_ys), size=n_trades)
            barrier = np.array(block_ys)[idx].astype(bool)
        for b in barrier:
            stake = f * eq
            eq = eq + (-LOSS_CASH * stake if b else WIN_CASH * stake)
            m = min(m, eq)
            if eq <= 0:
                eq = 0.0
                m = 0.0
                break
        min_eq.append(m / EQUITY0)
        for a in hits:
            if m / EQUITY0 < a:
                hits[a] += 1
    return {
        "n_sims": n_sims,
        "p_survival_assumed": p,
        "P_equity_below_80pct": hits[0.80] / n_sims,
        "P_equity_below_70pct": hits[0.70] / n_sims,
        "P_equity_below_50pct": hits[0.50] / n_sims,
        "median_min_equity_frac": float(np.median(min_eq)),
        "note": "Ruin is a defined capital-loss threshold, not a 0% claim from finite sims.",
    }


def same_day_dependence(rows):
    by = defaultdict(list)
    for r in rows:
        by[r.get("game_date")].append(int(r["Y_40_CLOSE"]))
    days = [v for v in by.values() if len(v) >= 2]
    if not days:
        return {"n_multi_days": 0}
    # mean intra-day pairwise product vs q^2
    q = float(np.mean([x for v in days for x in v]))
    pairs = []
    for v in days:
        arr = np.array(v, dtype=float)
        if len(arr) < 3:
            continue
        a, b = arr[:-1], arr[1:]
        if float(a.std()) <= 0 or float(b.std()) <= 0:
            continue
        pairs.append(float(np.corrcoef(a, b)[0, 1]))
    return {
        "n_multi_days": len(days),
        "mean_lag1_same_day_corr": float(np.nanmean(pairs)) if pairs else None,
        "unconditional_q_on_those_days": q,
        "note": "Trades on a slate are not assumed IID. Block bootstrap used in ruin.",
    }


def main() -> int:
    states = {r["trade_id"]: r for r in read_parquet_rows(OBS / "first80_game_state.parquet")}
    preds = read_parquet_rows(MODELS / "predictions.parquet")
    rows = []
    for p in preds:
        s = states[p["trade_id"]]
        rec = dict(s)
        rec.update(p)
        rows.append(rec)
    rng = np.random.default_rng(42)

    def subset(name):
        return [r for r in rows if r["dataset_split"] == name]

    tr, va, oo = subset("TRAIN"), subset("VALIDATION"), subset("OOS")
    p_cut = float(np.quantile([r["p_selected"] for r in tr], 0.75))
    skip_reg = ("B_FRAGILE_LEAD", "C_MARKET_SHOCK", "D_GAME_SHOCK", "E_TURBULENT")

    frontier = []
    policies = [
        ("hold_all", None, None),
        ("skip_high_p", p_cut, None),
        ("skip_fragile_regimes", None, skip_reg),
    ]
    split_eval = {}
    for split_name, chunk in (("TRAIN", tr), ("VALIDATION", va), ("OOS", oo)):
        split_eval[split_name] = {}
        for pname, cut, reg in policies:
            acc = policy_accept(chunk, pname, p_cut=cut, skip_regimes=reg)
            sizes = []
            for r, ok in zip(chunk, acc):
                if pname == "half_size_high_p" and cut is not None and r["p_selected"] > cut:
                    sizes.append(0.5)
                else:
                    sizes.append(1.0)
            rs, cash = apply_returns(chunk, acc, sizes)
            st = stats_R(rs)
            st["acceptance_rate"] = float(np.mean(acc)) if acc else 0.0
            st["n_accepted"] = int(sum(acc))
            st["mean_cash_mult"] = float(np.mean(cash)) if cash else None
            split_eval[split_name][pname] = st
            if split_name == "VALIDATION":
                frontier.append({"policy": pname, "split": split_name, **st, "p_cut": cut})

    # Fractional vs fixed-dollar on OOS hold-all
    def equity_sim(chunk, fractional=True, dd_schedule=False):
        eq = EQUITY0
        peak = eq
        path = [eq]
        for r in chunk:
            f = FRAC
            dd = 1.0 - eq / peak
            if dd_schedule:
                if dd >= 0.20:
                    f = 0.0
                elif dd >= 0.15:
                    f = FRAC * 0.25
                elif dd >= 0.10:
                    f = FRAC * 0.50
                elif dd >= 0.05:
                    f = FRAC * 0.75
            stake = f * (eq if fractional else EQUITY0)
            eq = eq + cash_mult(r["Y_40_CLOSE"]) * stake
            peak = max(peak, eq)
            path.append(eq)
        return path

    frac_path = equity_sim(oo, True, False)
    dollar_path = equity_sim(oo, False, False)
    dd_path = equity_sim(oo, True, True)

    p_hat = 1.0 - Q_UNCONDITIONAL
    f_star, g_star, curve = kelly_curve(p_hat)
    kelly_compare = {}
    for label, f in (
        ("full_kelly", f_star),
        ("half_kelly", 0.5 * f_star),
        ("quarter_kelly", 0.25 * f_star),
        ("fixed_2pct", FRAC),
    ):
        kelly_compare[label] = {"f": f, "g": float(p_hat * np.log(1 + WIN_CASH * f) + (1 - p_hat) * np.log(1 - LOSS_CASH * f))}

    n_tr = max(len(tr), 1)
    ruin = {}
    y_blocks = [int(r["Y_40_CLOSE"]) for r in tr]
    months = month_blocks(tr)
    for p in P_STRESS:
        ruin[str(p)] = ruin_paths(p, n_trades=n_tr, n_sims=2000, f=FRAC, rng=rng, block_ys=None)
        ruin[str(p)]["iid_assumption"] = True
    ruin["historical_trade_bootstrap"] = ruin_paths(
        p_hat, n_trades=n_tr, n_sims=2000, f=FRAC, rng=rng, block_ys=y_blocks
    )
    ruin["historical_trade_bootstrap"]["iid_assumption"] = False
    ruin["historical_block"] = ruin_paths(
        p_hat, n_trades=n_tr, n_sims=2000, f=FRAC, rng=rng, month_blocks_data=months
    )
    ruin["historical_block"]["iid_assumption"] = False
    ruin["historical_block"]["n_month_blocks"] = len(months)

    # Beta posterior sensitivity
    k_surv = 910
    k_fail = 320
    post = rng.beta(k_surv + 1, k_fail + 1, size=5000)
    ruin["beta_posterior_p"] = {
        "alpha": k_surv + 1,
        "beta": k_fail + 1,
        "p5": float(np.quantile(post, 0.05)),
        "p50": float(np.quantile(post, 0.50)),
        "p95": float(np.quantile(post, 0.95)),
    }

    q_grid = [0.26, 0.28, 0.30, 0.32, 0.3333, 0.36]
    edge = [
        {
            "q": q,
            "ev": ev_from_q(q),
            "margin": BREAKEVEN_Q - q,
            "breakeven": abs(q - BREAKEVEN_Q) < 1e-4,
        }
        for q in q_grid
    ]

    trade_ret_rows = [
        {
            "trade_id": r["trade_id"],
            "dataset_split": r["dataset_split"],
            "game_date": r.get("game_date"),
            "Y_40_CLOSE": r["Y_40_CLOSE"],
            "R": r_unit(r["Y_40_CLOSE"]),
            "cash_mult": cash_mult(r["Y_40_CLOSE"]),
            "p_selected": r["p_selected"],
            "regime": r.get("regime"),
        }
        for r in rows
    ]
    write_parquet(PORT / "trade_returns.parquet", trade_ret_rows)
    write_parquet(PORT / "policy_frontier.parquet", frontier)
    write_json(PORT / "policy_frontier.json", {"validation": frontier, "all_splits": split_eval})
    write_json(
        PORT / "drawdown_simulations.json",
        {
            "equity0": EQUITY0,
            "fraction": FRAC,
            "oos_fractional_terminal": frac_path[-1],
            "oos_fixed_dollar_terminal": dollar_path[-1],
            "oos_dd_schedule_terminal": dd_path[-1],
            "oos_fractional_min": min(frac_path),
            "oos_fixed_dollar_min": min(dollar_path),
            "chase_rejected": True,
            "note": "Default is fraction of current equity. Fixed-dollar is the chase-adjacent comparator.",
        },
    )
    write_json(PORT / "ruin_simulations.json", ruin)
    ruin_rows = []
    for k, v in ruin.items():
        if not isinstance(v, dict) or "P_equity_below_80pct" not in v:
            continue
        ruin_rows.append(
            {
                "scenario": k,
                "p_survival_assumed": v.get("p_survival_assumed"),
                "P_equity_below_80pct": v.get("P_equity_below_80pct"),
                "P_equity_below_70pct": v.get("P_equity_below_70pct"),
                "P_equity_below_50pct": v.get("P_equity_below_50pct"),
                "median_min_equity_frac": v.get("median_min_equity_frac"),
            }
        )
    write_parquet(PORT / "ruin_simulations.parquet", ruin_rows)
    write_parquet(
        PORT / "drawdown_simulations.parquet",
        [
            {"policy": "fractional_current_equity", "oos_terminal": frac_path[-1], "oos_min": min(frac_path)},
            {"policy": "fixed_dollar", "oos_terminal": dollar_path[-1], "oos_min": min(dollar_path)},
            {"policy": "drawdown_schedule", "oos_terminal": dd_path[-1], "oos_min": min(dd_path)},
        ],
    )
    write_json(
        PORT / "edge_decay.json",
        {
            "q0": Q_UNCONDITIONAL,
            "breakeven_q": BREAKEVEN_Q,
            "margin0": BREAKEVEN_Q - Q_UNCONDITIONAL,
            "grid": edge,
        },
    )
    payload = {
        "written_utc": utc_now(),
        "equity0_research": EQUITY0,
        "fraction_research": FRAC,
        "max_concurrent_research": MAX_CONCURRENT,
        "not_live_mlb_sizing": True,
        "p_cut_train_p75": p_cut,
        "splits": split_eval,
        "kelly": {
            "f_star_full": f_star,
            "g_star": g_star,
            "compare": kelly_compare,
            "research_only": True,
        },
        "dependence": same_day_dependence(rows),
        "ruin": ruin,
        "edge_decay": edge,
        "oos_equity": {
            "fractional": frac_path[-1],
            "fixed_dollar": dollar_path[-1],
            "dd_schedule": dd_path[-1],
        },
    }
    write_json(PORT / "portfolio_simulation.json", payload)
    write_json(REP / "portfolio_simulation.json", payload)
    print(
        f"portfolio VAL hold EV={split_eval['VALIDATION']['hold_all'].get('mean_R')} "
        f"skip_p EV={split_eval['VALIDATION']['skip_high_p'].get('mean_R')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
