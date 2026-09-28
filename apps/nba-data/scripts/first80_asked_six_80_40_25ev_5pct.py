#!/usr/bin/env python3
"""5% stake, compound, 10 bets/week, 22 weeks, planning EV +2.5¢.

Wins +20¢. Stop loss bag averages −49.1806¢ so that
(883×20 − 299×49.1806) / 1182 = +2.50¢ exactly.

```
RESEARCH ONLY
PLANNING EV +2.5¢ — NOT A FILL
LIVE EXECUTION = FALSE
DO NOT CHANGE LIVE FIRST01
40 STOP UNCHANGED
```

Stake = 5% of bankroll at 80¢. A −49¢ stop then costs ~3.1% of bankroll,
not 5%. Integer contracts. $20,000 start.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import first80_asked_six_80_40_liquidation as L  # noqa: E402

REPO = Path("/Users/user/Desktop/Momento")
OUT = REPO / "research" / "first80_asked_six_80_40_25ev_5pct"
WH_OUT = L.WH_OUT.parent / "first80_asked_six_80_40_25ev_5pct"

EXPECTED_N = 1182
EXPECTED_WIN = 883
EXPECTED_STOP = 299
B0_CENTS = 2_000_000
ENTRY_CENTS = 80
WIN_PNL = 20
F_PCT = 5
WEEKS = 22
TRADES_PER_WEEK = 10
N_TRADES = WEEKS * TRADES_PER_WEEK
N_PATHS = 80_000
SEED = 20260912
# 245 × 49 + 54 × 50 = 14,705 = 883×20 − 2.5×1182
STOP_LOSS_BAG = np.concatenate(
    [np.full(245, 49, dtype=np.int64), np.full(54, 50, dtype=np.int64)]
)


class IdentityHalt(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def planning_ev_cents() -> float:
    total = EXPECTED_WIN * WIN_PNL - int(STOP_LOSS_BAG.sum())
    if total != 2955:
        raise IdentityHalt(f"HALT ev numerator {total}")
    return total / EXPECTED_N


def qty_from_bankroll(b: np.ndarray, f_pct: int = F_PCT) -> np.ndarray:
    return np.maximum((b * int(f_pct) // 100) // ENTRY_CENTS, 0)


def summarize(end: np.ndarray, max_dd: np.ndarray, start: int = B0_CENTS) -> dict:
    years = WEEKS / 52.0
    ret = end.astype(np.float64) / float(start) - 1.0
    cagr = np.where(
        end > 0, (end.astype(np.float64) / float(start)) ** (1.0 / years) - 1.0, -1.0
    )
    return {
        "n_paths": int(end.size),
        "weeks": WEEKS,
        "trades": N_TRADES,
        "end_p50": int(np.median(end)),
        "end_mean": int(np.mean(end)),
        "end_p05": int(np.quantile(end, 0.05)),
        "end_p95": int(np.quantile(end, 0.95)),
        "cagr_p50": round(float(np.median(cagr)) * 100, 4),
        "p_ge_50pct_return": round(float((ret >= 0.50).mean()) * 100, 4),
        "p_lose_money": round(float((end < start).mean()) * 100, 4),
        "p_dd_gt_20": round(float((max_dd > 0.20).mean()) * 100, 4),
        "p_dd_gt_30": round(float((max_dd > 0.30).mean()) * 100, 4),
        "p_dd_gt_50": round(float((max_dd > 0.50).mean()) * 100, 4),
        "dd_p50": round(float(np.median(max_dd)) * 100, 4),
        "dd_p95": round(float(np.quantile(max_dd, 0.95)) * 100, 4),
        "dd_p99": round(float(np.quantile(max_dd, 0.99)) * 100, 4),
        "label": "PLANNING EV +2.5¢ — NOT A FILL",
    }


def simulate_per_bet(n_paths: int, rng: np.random.Generator) -> dict:
    """5% of current bankroll every trade. Compound each bet."""
    p = EXPECTED_WIN / EXPECTED_N
    wins = rng.random((n_paths, N_TRADES)) < p
    losses = rng.choice(STOP_LOSS_BAG, size=(n_paths, N_TRADES), replace=True)
    pnl = np.where(wins, WIN_PNL, -losses)
    b = np.full(n_paths, B0_CENTS, dtype=np.int64)
    peak = b.copy()
    max_dd = np.zeros(n_paths, dtype=np.float64)
    for t in range(N_TRADES):
        qty = qty_from_bankroll(b)
        b = np.maximum(b + qty * pnl[:, t], 0)
        peak = np.maximum(peak, b)
        dd = np.where(peak > 0, (peak - b) / peak.astype(np.float64), 0.0)
        max_dd = np.maximum(max_dd, dd)
    stats = summarize(b, max_dd)
    stats["mode"] = "per_bet_compound"
    return stats


def simulate_week_start(n_paths: int, rng: np.random.Generator) -> dict:
    """5% of week-start bankroll. Same qty for 10 bets, then compound."""
    p = EXPECTED_WIN / EXPECTED_N
    wins = rng.random((n_paths, WEEKS, TRADES_PER_WEEK)) < p
    losses = rng.choice(
        STOP_LOSS_BAG, size=(n_paths, WEEKS, TRADES_PER_WEEK), replace=True
    )
    pnl = np.where(wins, WIN_PNL, -losses)
    b = np.full(n_paths, B0_CENTS, dtype=np.int64)
    peak = b.copy()
    max_dd = np.zeros(n_paths, dtype=np.float64)
    for w in range(WEEKS):
        qty = qty_from_bankroll(b)
        wp = qty * pnl[:, w, :].sum(axis=1)
        b = np.maximum(b + wp, 0)
        peak = np.maximum(peak, b)
        dd = np.where(peak > 0, (peak - b) / peak.astype(np.float64), 0.0)
        max_dd = np.maximum(max_dd, dd)
    stats = summarize(b, max_dd)
    stats["mode"] = "week_start_compound"
    return stats


def deterministic_mean_path() -> dict:
    """Every trade earns exactly +2.5¢ per contract. Integer qty."""
    ev = planning_ev_cents()
    b_floor = B0_CENTS
    for _ in range(N_TRADES):
        qty = (b_floor * F_PCT // 100) // ENTRY_CENTS
        b_floor = max(b_floor + qty * 5 // 2, 0)
    frac = (F_PCT / 100.0) * (ev / ENTRY_CENTS)
    closed = B0_CENTS / 100.0 * (1.0 + frac) ** N_TRADES
    return {
        "ev_cents": ev,
        "growth_per_trade": frac,
        "closed_form_end_dollars": round(closed, 2),
        "integer_halfcent_end_cents": b_floor,
        "note": "Mean path only. Variance is the simulation.",
    }


def fmt_money(cents: int) -> str:
    return f"${cents / 100:,.0f}"


def write_report(doc: dict) -> str:
    bet = doc["per_bet"]
    week = doc["week_start"]
    det = doc["deterministic"]
    return "\n".join(
        [
            "# 5% stake · +2.5¢ EV · 10 bets/week · 22 weeks",
            "",
            "```",
            "RESEARCH ONLY",
            "PLANNING EV +2.5¢ — NOT A FILL",
            "LIVE EXECUTION = FALSE",
            "40 STOP UNCHANGED",
            "DO NOT CHANGE LIVE FIRST01",
            "```",
            "",
            f"Generated: `{doc['generated_at']}`",
            "",
            "## Setup",
            "",
            f"- Start **{fmt_money(B0_CENTS)}**",
            "- Stake **5%** of bankroll at 80¢. `qty = floor(0.05 × B / 80)`",
            "- A −49¢ stop then costs about **3.1%** of bankroll, not 5%",
            f"- 10 bets/week × {WEEKS} weeks = **{N_TRADES}** trades (~5 months)",
            f"- Planning EV **+{planning_ev_cents():.2f}¢**/contract "
            "(883 × +20 and a −49/−50 stop bag)",
            "- p = 883/1182. Not a Kalshi fill.",
            "",
            f"Closed-form mean if every trade earns exactly 2.5¢: "
            f"**${det['closed_form_end_dollars']:,.0f}** "
            f"({(1 + det['growth_per_trade']) ** N_TRADES - 1:.1%} on the fraction).",
            "",
            "## Per-bet compound (resize every trade)",
            "",
            "| | |",
            "|---|---:|",
            f"| Median end | **{fmt_money(bet['end_p50'])}** |",
            f"| Mean end | {fmt_money(bet['end_mean'])} |",
            f"| P5 / P95 | {fmt_money(bet['end_p05'])} / {fmt_money(bet['end_p95'])} |",
            f"| CAGR p50 | {bet['cagr_p50']:.1f}% |",
            f"| P(≥50% return) | {bet['p_ge_50pct_return']:.1f}% |",
            f"| P(lose money) | {bet['p_lose_money']:.2f}% |",
            f"| P(DD>20%) | {bet['p_dd_gt_20']:.1f}% |",
            f"| P(DD>30%) | {bet['p_dd_gt_30']:.1f}% |",
            f"| DD p50 / p95 / p99 | {bet['dd_p50']:.1f}% / {bet['dd_p95']:.1f}% / {bet['dd_p99']:.1f}% |",
            "",
            "## Week-start compound (same size for the 10 bets, then resize)",
            "",
            "| | |",
            "|---|---:|",
            f"| Median end | **{fmt_money(week['end_p50'])}** |",
            f"| Mean end | {fmt_money(week['end_mean'])} |",
            f"| P5 / P95 | {fmt_money(week['end_p05'])} / {fmt_money(week['end_p95'])} |",
            f"| CAGR p50 | {week['cagr_p50']:.1f}% |",
            f"| P(≥50% return) | {week['p_ge_50pct_return']:.1f}% |",
            f"| P(lose money) | {week['p_lose_money']:.2f}% |",
            f"| P(DD>20%) | {week['p_dd_gt_20']:.1f}% |",
            f"| DD p50 / p95 / p99 | {week['dd_p50']:.1f}% / {week['dd_p95']:.1f}% / {week['dd_p99']:.1f}% |",
            "",
            "This is slower than the clean −40¢ 5% grid (~$36k median) because",
            "the working EV is +2.5¢, not +4.82¢.",
            "",
            "## Does not",
            "",
            "- Change live FIRST01.",
            "- Prove a 40¢ fill.",
            "- Move the stop to 45.",
            "",
        ]
    ) + "\n"


def main() -> int:
    ev = planning_ev_cents()
    if abs(ev - 2.5) > 1e-9:
        raise IdentityHalt(f"HALT ev {ev}")
    rng1 = np.random.default_rng(SEED)
    rng2 = np.random.default_rng(SEED + 1)
    print("simulating per-bet compound…", flush=True)
    per_bet = simulate_per_bet(N_PATHS, rng1)
    print("simulating week-start compound…", flush=True)
    week = simulate_week_start(N_PATHS, rng2)
    det = deterministic_mean_path()
    doc = {
        "generated_at": utc_now(),
        "planning_ev_cents": ev,
        "f_pct": F_PCT,
        "start_cents": B0_CENTS,
        "weeks": WEEKS,
        "trades": N_TRADES,
        "seed": SEED,
        "n_paths": N_PATHS,
        "deterministic": det,
        "per_bet": per_bet,
        "week_start": week,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    WH_OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(doc, indent=2) + "\n")
    (OUT / "REPORT.md").write_text(write_report(doc))
    for fn in ("summary.json", "REPORT.md"):
        (WH_OUT / fn).write_text((OUT / fn).read_text())
    print(
        f"EV={ev} per-bet median={per_bet['end_p50']} "
        f"week median={week['end_p50']} "
        f"closed={det['closed_form_end_dollars']}"
    )
    print(f"wrote {OUT / 'REPORT.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
