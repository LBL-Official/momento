#!/usr/bin/env python3
"""Calculate the T4–B6 lead≥2 first-touch 80→55 / hold book.

Does not edit first80.py, compiler, execute, or load_dataset.
Candle path ≠ fill. Settlement is Kalshi result (100¢ / 0¢).
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from roller.research_query.execute import execute_question
from roller.results_math.payoff import decompose

ROOT = Path(__file__).resolve().parent
ENTRY_CENTS = 80
WIN_SETTLE_CENTS = 100
LOSS_BARRIER_CENTS = 55


def _cents_from_e4(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value) // 100
    except (TypeError, ValueError):
        return None


def main() -> int:
    payload = json.loads((ROOT / "draft_80_55_hold.json").read_text(encoding="utf-8"))
    env = execute_question(payload)
    trades = ((env.get("population") or {}).get("trades")) or []
    counts: Counter[str] = Counter()
    barrier_payoffs: list[int] = []
    observed_payoffs: list[int] = []
    observed_loss: list[int] = []
    missing_observed = 0
    for row in trades:
        outcome = str(row.get("exit_outcome") or "")
        counts[outcome] += 1
        if outcome == "WIN_EXIT":
            barrier_payoffs.append(WIN_SETTLE_CENTS - ENTRY_CENTS)
            entry_cents = _cents_from_e4(row.get("entry_close"))
            if entry_cents is None:
                missing_observed += 1
                continue
            observed_payoffs.append(WIN_SETTLE_CENTS - entry_cents)
        elif outcome == "LOSS_EXIT":
            barrier_payoffs.append(LOSS_BARRIER_CENTS - ENTRY_CENTS)
            hyp = row.get("hyp_pnl_cents")
            if hyp is None:
                missing_observed += 1
                continue
            observed_payoffs.append(int(hyp))
            observed_loss.append(int(hyp))
    win_n = counts["WIN_EXIT"]
    loss_n = counts["LOSS_EXIT"]
    classified = win_n + loss_n
    n = len(trades)
    barrier = decompose(
        win_n=win_n,
        loss_n=loss_n,
        win_payoff_cents=WIN_SETTLE_CENTS - ENTRY_CENTS,
        loss_payoff_cents=LOSS_BARRIER_CENTS - ENTRY_CENTS,
    )
    barrier_sum = sum(barrier_payoffs)
    observed_sum = sum(observed_payoffs)
    out = {
        "id": "mlb_t4b6_lead2_ft80_drop55_hold_ev",
        "execution_status": env.get("execution_status"),
        "observation_basis": env.get("observation_basis"),
        "n": n,
        "win_exit": win_n,
        "loss_exit": loss_n,
        "unclassified": n - classified,
        "classified": classified,
        "exit_counts": dict(counts),
        "barrier_book": {
            "status": "HYPOTHETICAL",
            "entry_cents": ENTRY_CENTS,
            "win_exit_cents": WIN_SETTLE_CENTS,
            "loss_exit_cents": LOSS_BARRIER_CENTS,
            "win_payoff_cents": WIN_SETTLE_CENTS - ENTRY_CENTS,
            "loss_payoff_cents": LOSS_BARRIER_CENTS - ENTRY_CENTS,
            "formula": "WIN +20¢ (hold 80→100) / LOSS −25¢ (drop to 55)",
            "sum_cents": barrier_sum,
            "ev_on_classified_cents": (barrier_sum / classified) if classified else None,
            "ev_on_n_cents": (barrier_sum / n) if n else None,
            "decompose": barrier,
            "note": "Assumes exact 80 entry and exact 55 exit. Candle path ≠ fill.",
        },
        "observed_book": {
            "status": "HYPOTHETICAL",
            "win_payoff": "100¢ − actual entry_close",
            "loss_payoff": "hyp_pnl_cents = (exit_close − entry_close) // 100",
            "n_with_payoff": len(observed_payoffs),
            "missing_observed": missing_observed,
            "sum_cents": observed_sum,
            "ev_cents": (observed_sum / len(observed_payoffs)) if observed_payoffs else None,
            "loss_n": len(observed_loss),
            "loss_sum_cents": sum(observed_loss) if observed_loss else 0,
            "loss_mean_cents": (sum(observed_loss) / len(observed_loss)) if observed_loss else None,
            "note": "Hold uses Kalshi settlement 100¢ vs the actual entry close. Stop uses the first ≤55¢ candle close. Candle path ≠ fill.",
        },
        "note": "CANDLE PATH ≠ FILL. MEASUREMENT ≠ EDGE. Not live trading.",
    }
    dest = ROOT / "report_80_55_ev.json"
    dest.write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2, default=str))
    return 0 if env.get("execution_status") == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
