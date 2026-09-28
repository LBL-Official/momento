#!/usr/bin/env python3
"""Stress the combined FIRST80 book: dependence, caps, week blocks.

Research only. Does not change live FIRST01. Zero fee. Candle path.

The 6+6 book is a new portfolio (max 60% SOD), not extra NBA bets.
This script answers the missing tests:

1. Empirical same-night NBA↔NCAAB tail dependence on the 82 overlap days.
2. Cap architectures: 6+6 (60%), combined-6 (30%), hierarchical-8 (40%).
3. Shared daily-factor stress on both-sport nights (tail dependence).
4. Week-block bootstrap of the 2025-26 joint weeks (keeps last year’s
   clustering and whatever cross-sport dependence the tape actually had).

Sports remain P5 H1_2∪H2_1 and NBA Q2∪Q3. 50/30/20 slip. 3.000% haircut.
Does not invent L2 or 76-team extra prints.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np

SCRIPTS = Path(__file__).resolve().parent
NCAAB_SCRIPTS = Path("/Users/user/Desktop/Momento/apps/ncaab-data/scripts")
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
if str(NCAAB_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(NCAAB_SCRIPTS))

import first80_dual_sport_novapr_portfolio_sim as D  # noqa: E402
import first80_p5_h12_h21_profit_likelihood as NC  # noqa: E402
import first80_q23_novapr_portfolio_sim as NBA  # noqa: E402

OUT = D.OUT.parent / "first80_dual_sport_portfolio_stress"

N_SIM = 8_000
SEED = 20260905
FACTOR_ALPHAS = (0.00, 0.05, 0.10, 0.15, 0.20)
HIER_TOTAL = 8
COMBINED_TOTAL = 6

# Locked from the 82 both-sport days (capped 6/sport).
EXPECTED_BOTH_DAYS = 82
EXPECTED_JOINT_BELOW_TWO_THIRDS = 2
EXPECTED_ARCH = {
    "cap_6_plus_6": {"taken": 768, "nba": 499, "ncaab": 269, "max": 12},
    "cap_combined_6": {"taken": 668, "nba": 427, "ncaab": 241, "max": 6},
    "cap_hier_8": {"taken": 729, "nba": 470, "ncaab": 259, "max": 8},
}


class IdentityHalt(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rows_by_day() -> tuple[list[date], dict, dict]:
    nba_rows = NBA.window_rows()
    ncaab_rows = NC.load_book_rows()
    days = NBA.calendar_days(D.WINDOW_START, D.WINDOW_END)
    nba_by: dict[date, list] = defaultdict(list)
    ncaab_by: dict[date, list] = defaultdict(list)
    for r in nba_rows:
        nba_by[NBA.game_date_of(r)].append(r)
    for r in ncaab_rows:
        ncaab_by[date.fromisoformat(str(r["game_date"])[:10])].append(r)
    return days, nba_by, ncaab_by


def _key(r: dict) -> tuple[int, str]:
    return (int(r["first_80_timestamp"]), str(r.get("ticker") or r.get("event_id")))


def _cap_sport(rs: list[dict], n: int = 6) -> list[dict]:
    return sorted(rs, key=_key)[:n]


def _pool(d: date, nba_by: dict, ncaab_by: dict) -> list[tuple[int, int, str, str, dict]]:
    items = []
    for r in nba_by[d]:
        ts, tid = _key(r)
        items.append((ts, 0, tid, "nba", r))
    for r in ncaab_by[d]:
        ts, tid = _key(r)
        items.append((ts, 1, tid, "ncaab", r))
    items.sort()
    return items


def p_bar(rs: list[dict]) -> float:
    return sum(1 for r in rs if r["W"] and not r["T40"]) / len(rs)


def empirical_same_night(days, nba_by, ncaab_by) -> dict:
    both = []
    for d in days:
        a = _cap_sport(nba_by[d])
        b = _cap_sport(ncaab_by[d])
        if a and b:
            both.append((d, a, b, p_bar(a), p_bar(b)))
    if len(both) != EXPECTED_BOTH_DAYS:
        raise IdentityHalt(f"HALT both {len(both)}")
    pa = np.array([x[3] for x in both], dtype=np.float64)
    pb = np.array([x[4] for x in both], dtype=np.float64)
    pearson = float(np.corrcoef(pa, pb)[0, 1])
    rx = pa.argsort().argsort().astype(np.float64)
    ry = pb.argsort().argsort().astype(np.float64)
    spearman = float(np.corrcoef(rx, ry)[0, 1])

    def joint(thr: float) -> dict:
        ba = pa < thr
        bb = pb < thr
        n_both = int((ba & bb).sum())
        p_a = float(ba.mean())
        p_b = float(bb.mean())
        return {
            "threshold": thr,
            "n_nba_bad": int(ba.sum()),
            "n_ncaab_bad": int(bb.sum()),
            "n_joint_bad": n_both,
            "p_nba_bad": p_a,
            "p_ncaab_bad": p_b,
            "p_joint": float(n_both / len(both)),
            "p_joint_if_independent": p_a * p_b,
            "p_nba_given_ncaab_bad": (float(n_both / int(bb.sum())) if bb.any() else None),
            "p_ncaab_given_nba_bad": (float(n_both / int(ba.sum())) if ba.any() else None),
        }

    j23 = joint(2.0 / 3.0)
    if j23["n_joint_bad"] != EXPECTED_JOINT_BELOW_TWO_THIRDS:
        raise IdentityHalt(f"HALT joint 2/3 {j23}")
    ge3 = [(x[3], x[4]) for x in both if len(x[1]) >= 3 and len(x[2]) >= 3]
    pearson_ge3 = float(np.corrcoef(*zip(*ge3))[0, 1]) if len(ge3) > 2 else None
    return {
        "n_both_sport_days": len(both),
        "mean_p_bar_nba": float(pa.mean()),
        "mean_p_bar_ncaab": float(pb.mean()),
        "pearson_p_bar": pearson,
        "spearman_p_bar": spearman,
        "n_days_ge3_each": len(ge3),
        "pearson_p_bar_ge3_each": pearson_ge3,
        "joint_below_two_thirds": j23,
        "joint_below_0_60": joint(0.60),
        "joint_below_0_50": joint(0.50),
        "joint_below_slip_be": joint(0.704),
        "note": (
            "Point estimate is slightly negative. n=82 is small. Joint "
            "p_bar<2/3 nights (2) were fewer than the independence product "
            "(~3.6). This does not prove diversification; it fails to show "
            "positive same-night tail dependence in 2025-26."
        ),
    }


def architecture_taken(days, nba_by, ncaab_by) -> dict:
    def lists_for(kind: str) -> tuple[list[int], list[int]]:
        nba_t = []
        ncaab_t = []
        for d in days:
            if kind == "cap_6_plus_6":
                nba_t.append(len(_cap_sport(nba_by[d], 6)))
                ncaab_t.append(len(_cap_sport(ncaab_by[d], 6)))
                continue
            total = COMBINED_TOTAL if kind == "cap_combined_6" else HIER_TOTAL
            cn = cc = 0
            for *_, s, _r in _pool(d, nba_by, ncaab_by):
                if cn + cc >= total:
                    break
                if s == "nba" and cn >= 6:
                    continue
                if s == "ncaab" and cc >= 6:
                    continue
                if s == "nba":
                    cn += 1
                else:
                    cc += 1
            nba_t.append(cn)
            ncaab_t.append(cc)
        return nba_t, ncaab_t

    out = {}
    for kind, exp in EXPECTED_ARCH.items():
        nba_t, ncaab_t = lists_for(kind)
        taken = [a + b for a, b in zip(nba_t, ncaab_t)]
        rec = {
            "nba_taken": nba_t,
            "ncaab_taken": ncaab_t,
            "taken": taken,
            "n_taken": int(sum(taken)),
            "n_nba": int(sum(nba_t)),
            "n_ncaab": int(sum(ncaab_t)),
            "max_taken": int(max(taken)),
            "max_sod_pct": int(max(taken)) * D.FRACTION_PCT,
            "days_at_max": int(sum(1 for n in taken if n == max(taken))),
        }
        if rec["n_taken"] != exp["taken"] or rec["n_nba"] != exp["nba"]:
            raise IdentityHalt(f"HALT {kind} {rec['n_taken']} {rec['n_nba']}")
        if rec["n_ncaab"] != exp["ncaab"] or rec["max_taken"] != exp["max"]:
            raise IdentityHalt(f"HALT {kind} max {rec}")
        out[kind] = rec
    return out


def pack_terminal(end: np.ndarray, min_b: np.ndarray, max_dd: np.ndarray) -> dict:
    return {
        "taken_note": None,
        "terminal": NBA.terminal_distribution(end, D.B0),
        "risk_of_ruin": {
            "p_end_below_start": round(float((end < D.B0).mean()), 4),
            "p_touch_50pct_start": round(float((min_b < D.B0 * 50 // 100).mean()), 4),
            "p_peak_dd_ge_50pct": round(float((max_dd >= 5000).mean()), 4),
            "median_max_dd_pct": round(float(np.median(max_dd)) / 100.0, 2),
            "p95_max_dd_pct": round(float(np.quantile(max_dd, 0.95)) / 100.0, 2),
        },
    }


def simulate_arch(nba_t: list[int], ncaab_t: list[int], days: list[date], seed: int) -> dict:
    sim = D.simulate(nba_t, ncaab_t, days, n_sim=N_SIM, seed=seed)
    out = pack_terminal(sim["end_cents"], sim["min_cents"], sim["max_dd_bp"])
    out["n_trades"] = sim["n_trades"]
    out["naive_3pct_end_dollars"] = NBA.dollars(D.naive_3pct_end_cents([a + b for a, b in zip(nba_t, ncaab_t)]))
    return out


def _class_probs(p_s: float, q_wt: float) -> np.ndarray:
    p_s = float(np.clip(p_s, 0.02, 0.98))
    rem = 1.0 - p_s
    p_wt = rem * q_wt
    p_l = rem * (1.0 - q_wt)
    return np.array([p_s, p_wt, p_l * 0.50, p_l * 0.30, p_l * 0.20], dtype=np.float64)


def simulate_shared_factor(
    nba_t: list[int],
    ncaab_t: list[int],
    days: list[date],
    alpha: float,
    seed: int,
) -> dict:
    """Same daily ε shifts both sports’ P(¬T40) on both-sport nights.

    α is the standard deviation of the shared shock in probability points.
    α=0 is independence. α=0.20 is a ±20pp 1σ joint move.
    """
    sports, day_n = D.trade_schedule(nba_t, ncaab_t)
    n_sim = N_SIM
    rng = np.random.default_rng(seed)
    n_trades = int(day_n.sum())
    pnl = np.empty((n_sim, n_trades), dtype=np.int64)
    p0_nba = 450 / 604
    p0_nc = 250 / 332
    q_nba = 55 / 154
    q_nc = 31 / 82
    cursor = 0
    for a, b, n in zip(nba_t, ncaab_t, day_n.tolist()):
        both = a > 0 and b > 0
        if n == 0:
            continue
        if both and alpha > 0:
            eps = rng.normal(0.0, 1.0, size=n_sim)
            p_nba = np.clip(p0_nba + alpha * eps, 0.02, 0.98)
            p_nc = np.clip(p0_nc + alpha * eps, 0.02, 0.98)
        else:
            p_nba = np.full(n_sim, p0_nba)
            p_nc = np.full(n_sim, p0_nc)
        sl = sports[cursor : cursor + n]
        for j, sport in enumerate(sl.tolist()):
            p = p_nba if sport == D.SPORT_NBA else p_nc
            q = q_nba if sport == D.SPORT_NBA else q_nc
            # Per-path multinomial of 1 = categorical.
            # Vectorized: draw U and invert the cdf of the 5-class mix.
            u = rng.random(n_sim)
            # Build thresholds from p,q — q is scalar, p varies.
            rem = 1.0 - p
            p_wt = rem * q
            p_l40 = rem * (1.0 - q) * 0.50
            p_l20 = rem * (1.0 - q) * 0.30
            edges = np.stack(
                [p, p + p_wt, p + p_wt + p_l40, p + p_wt + p_l40 + p_l20],
                axis=1,
            )
            cls = np.zeros(n_sim, dtype=np.int64)
            cls = cls + (u >= edges[:, 0])
            cls = cls + (u >= edges[:, 1])
            cls = cls + (u >= edges[:, 2])
            cls = cls + (u >= edges[:, 3])
            pnl[:, cursor + j] = D.PNL_TABLE[cls]
        cursor += n
    b = np.full(n_sim, D.B0, dtype=np.int64)
    peak = b.copy()
    min_b = b.copy()
    max_dd = np.zeros(n_sim, dtype=np.int64)
    cursor = 0
    for n in day_n.tolist():
        if n:
            contracts = (b * D.FRACTION_PCT // 100) // D.ENTRY
            raw = contracts[:, None] * pnl[:, cursor : cursor + n]
            adj = D.apply_sport_edge(raw, sports[cursor : cursor + n])
            b = b + adj.sum(axis=1)
            cursor += n
        min_b = np.minimum(min_b, b)
        peak = np.maximum(peak, b)
        dd = np.where(peak > 0, (peak - b) * 10000 // peak, 0)
        max_dd = np.maximum(max_dd, dd)
    out = pack_terminal(b, min_b, max_dd)
    out["alpha"] = alpha
    out["n_trades"] = n_trades
    return out


def historical_weeks(days, nba_by, ncaab_by) -> list[list[list[tuple[int, int | None]]]]:
    """24 weeks of days; each day is (sport, class or None=loser)."""

    def cls(r: dict) -> int | None:
        if r["W"] and not r["T40"]:
            return 0
        if r["W"] and r["T40"]:
            return 1
        return None

    weeks: dict[tuple[int, int], list] = defaultdict(list)
    order = []
    seen = set()
    for d in days:
        k = NBA.iso_week_key(d)
        if k not in seen:
            seen.add(k)
            order.append(k)
        nba = _cap_sport(nba_by[d], 6)
        nca = _cap_sport(ncaab_by[d], 6)
        trades = [(D.SPORT_NBA, cls(r)) for r in nba] + [(D.SPORT_NCAAB, cls(r)) for r in nca]
        weeks[k].append(trades)
    return [weeks[k] for k in order]


def simulate_week_bootstrap(week_days: list, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    n_sim = N_SIM
    n_weeks = len(week_days)
    idx = rng.integers(0, n_weeks, size=(n_sim, n_weeks))
    b = np.full(n_sim, D.B0, dtype=np.int64)
    peak = b.copy()
    min_b = b.copy()
    max_dd = np.zeros(n_sim, dtype=np.int64)
    n_tr = []
    for i in range(n_sim):
        bb = D.B0
        pk = bb
        mn = bb
        dd = 0
        nt = 0
        for w in idx[i]:
            for trades in week_days[int(w)]:
                if not trades:
                    continue
                contracts = (bb * D.FRACTION_PCT // 100) // D.ENTRY
                raw = 0
                for sport, c in trades:
                    nt += 1
                    if c is None:
                        n40 = 1 if rng.random() < 0.50 else 0
                        n20 = 1 if (n40 == 0 and rng.random() < 0.60) else 0
                        n10 = 1 - n40 - n20
                        pnl = n40 * (-40) + n20 * (-60) + n10 * (-70)
                    else:
                        pnl = int(D.PNL_TABLE[c])
                    num, den = (
                        (NBA.EDGE_SCALE_NUM, NBA.EDGE_SCALE_DEN)
                        if sport == D.SPORT_NBA
                        else (D.NCAAB_EDGE_NUM, D.NCAAB_EDGE_DEN)
                    )
                    raw += int(D.scale_edge(np.array([contracts * pnl]), num, den)[0])
                bb += raw
                mn = min(mn, bb)
                pk = max(pk, bb)
                if pk > 0:
                    dd = max(dd, (pk - bb) * 10000 // pk)
        b[i] = bb
        min_b[i] = mn
        max_dd[i] = dd
        n_tr.append(nt)
    out = pack_terminal(b, min_b, max_dd)
    out["n_trades_mean"] = float(np.mean(n_tr))
    return out


def analyze(n_sim: int = N_SIM, seed: int = SEED) -> dict:
    global N_SIM
    N_SIM = n_sim
    days, nba_by, ncaab_by = _rows_by_day()
    emp = empirical_same_night(days, nba_by, ncaab_by)
    arch = architecture_taken(days, nba_by, ncaab_by)
    caps = {}
    for i, kind in enumerate(("cap_6_plus_6", "cap_combined_6", "cap_hier_8")):
        rec = arch[kind]
        sim = simulate_arch(rec["nba_taken"], rec["ncaab_taken"], days, seed + 10 + i)
        sim["n_taken"] = rec["n_taken"]
        sim["n_nba"] = rec["n_nba"]
        sim["n_ncaab"] = rec["n_ncaab"]
        sim["max_sod_pct"] = rec["max_sod_pct"]
        caps[kind] = sim
    factors = []
    for j, a in enumerate(FACTOR_ALPHAS):
        rec = arch["cap_6_plus_6"]
        sim = simulate_shared_factor(rec["nba_taken"], rec["ncaab_taken"], days, a, seed + 50 + j)
        factors.append(sim)
    weeks = historical_weeks(days, nba_by, ncaab_by)
    if len(weeks) != 24:
        raise IdentityHalt(f"HALT weeks {len(weeks)}")
    boot = simulate_week_bootstrap(weeks, seed + 80)
    return {
        "written_utc": utc_now(),
        "research_only": True,
        "live_first01_unchanged": True,
        "fee_cents": 0,
        "n_sim": n_sim,
        "seed": seed,
        "label": (
            "$57,456 and 3.44 Sharpe are IID independent-sport research "
            "outputs — not a robust portfolio forecast."
        ),
        "empirical_same_night": emp,
        "architectures": {
            kind: {
                "n_taken": arch[kind]["n_taken"],
                "n_nba": arch[kind]["n_nba"],
                "n_ncaab": arch[kind]["n_ncaab"],
                "max_taken": arch[kind]["max_taken"],
                "max_sod_pct": arch[kind]["max_sod_pct"],
                **{k: caps[kind][k] for k in ("terminal", "risk_of_ruin", "naive_3pct_end_dollars")},
            }
            for kind in caps
        },
        "shared_daily_factor": factors,
        "week_block_bootstrap": boot,
        "financial_behavior": [
            "6+6 raises max SOD exposure from 30% to 60%. That is a new book.",
            "combined-6 restores the 30% night and drops 100 prints (768→668).",
            "hier-8 is a portfolio cap: ≤6/sport and ≤8 total (40% SOD).",
            "Shared-factor α>0 makes both sports miss 40 together on overlap nights.",
            "Week bootstrap keeps last year’s joint weeks; it does not invent ρ.",
        ],
    }


def write_outputs(summary: dict) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "summary.json"
    path.write_text(json.dumps(summary, indent=2) + "\n")
    print("wrote", path)
    emp = summary["empirical_same_night"]
    print("pearson", round(emp["pearson_p_bar"], 3), "joint<2/3", emp["joint_below_two_thirds"]["n_joint_bad"])
    for k, rec in summary["architectures"].items():
        t = rec["terminal"]["percentiles_dollars"]
        print(k, rec["n_taken"], "p50", t["p50"], "p05", t["p05"], "P<start", rec["risk_of_ruin"]["p_end_below_start"])
    for rec in summary["shared_daily_factor"]:
        t = rec["terminal"]["percentiles_dollars"]
        print("alpha", rec["alpha"], "p50", t["p50"], "p05", t["p05"], "P<start", rec["risk_of_ruin"]["p_end_below_start"], "p95DD", rec["risk_of_ruin"]["p95_max_dd_pct"])
    b = summary["week_block_bootstrap"]
    print("week boot p50", b["terminal"]["percentiles_dollars"]["p50"], "P<start", b["risk_of_ruin"]["p_end_below_start"])
    return path


def main() -> None:
    write_outputs(analyze())


if __name__ == "__main__":
    main()
