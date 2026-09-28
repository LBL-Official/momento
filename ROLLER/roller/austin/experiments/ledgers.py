"""Three distinct ledgers: HOLD, 8040, hypothetical intervention."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from roller.austin.experiments.ids import FILL_STATUS
from roller.austin.experiments.outcomes_ncaab import baseline_8040_cents, baseline_hold_cents
from roller.austin.experiments.policies import POLICY_FAMILY, decide
from roller.austin.paths import experiment_dir

SCENARIO_LABEL = "SCENARIO — NOT OBSERVED FILL"


def _write(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name) for name in fields})


def hold_rows(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for trade in trades:
        pnl = baseline_hold_cents(trade)
        out.append(
            {
                "trade_id": trade["trade_id"],
                "internal_game_id": trade.get("internal_game_id"),
                "ledger": "BASELINE_HOLD",
                "won": trade.get("won"),
                "t40": trade.get("t40"),
                "pnl_cents": pnl,
                "entry_timestamp": trade.get("entry_timestamp"),
            }
        )
    return out


def choosin_8040_rows(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for trade in trades:
        out.append(
            {
                "trade_id": trade["trade_id"],
                "internal_game_id": trade.get("internal_game_id"),
                "ledger": "BASELINE_8040",
                "won": trade.get("won"),
                "t40": trade.get("t40"),
                "pnl_cents": baseline_8040_cents(trade),
                "entry_timestamp": trade.get("entry_timestamp"),
            }
        )
    return out


def _scenario_prices(row: dict[str, Any], later: list[dict[str, Any]]) -> dict[str, int | None]:
    observed = row.get("current_price_cents")
    nxt = None
    for item in later:
        if item.get("current_price_cents") is not None:
            nxt = int(item["current_price_cents"])
            break
    a = None if observed is None else int(observed)
    b = nxt if nxt is not None else a
    if a is None and b is None:
        c = None
    else:
        c = max(1, min(x for x in (a, b) if x is not None) - 5)
    return {"scenario_a": a, "scenario_b": b, "scenario_c": c}


def _hyp_pnl(exit_price: int | None, won: bool) -> int | None:
    if exit_price is None:
        return None
    # Favorite sold at exit_price: recover exit, vs hold +20/-80.
    # Hypothetical remaining: exit_price - 80.
    return int(exit_price) - 80


def policy_rows(
    trades: list[dict[str, Any]],
    queries: list[dict[str, Any]],
    *,
    policy_ids: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_trade: dict[str, list[dict[str, Any]]] = {}
    for row in queries:
        by_trade.setdefault(row["trade_id"], []).append(row)
    trade_map = {t["trade_id"]: t for t in trades}
    ledgers = []
    interventions = []
    for policy_id in policy_ids:
        for trade in trades:
            rows = [r for r in by_trade.get(trade["trade_id"], [])]
            primary = [r for r in rows if r.get("primary")]
            action = "NONE"
            chosen = None
            for row in primary:
                decision = decide(
                    policy_id,
                    ev=None if row.get("conditional_ev_cents") is None else float(row["conditional_ev_cents"]),
                    ci_lower=None if row.get("ci_lower_cents") is None else float(row["ci_lower_cents"]),
                    ci_upper=None if row.get("ci_upper_cents") is None else float(row["ci_upper_cents"]),
                    ev_entry=None if row.get("ev_at_entry") is None else float(row["ev_at_entry"]),
                    primary=True,
                )
                if decision == "INTERVENE":
                    action = "INTERVENE"
                    chosen = row
                    break
            hold = baseline_hold_cents(trade)
            later = []
            if chosen is not None:
                later = [r for r in primary if (r.get("timestamp_utc") or "") > (chosen.get("timestamp_utc") or "")]
            prices = _scenario_prices(chosen or {}, later)
            hyp_b = _hyp_pnl(prices["scenario_b"], bool(trade.get("won"))) if action == "INTERVENE" else hold
            ledgers.append(
                {
                    "trade_id": trade["trade_id"],
                    "internal_game_id": trade.get("internal_game_id"),
                    "policy_id": policy_id,
                    "intervention": action,
                    "baseline_hold_pnl": hold,
                    "baseline_8040_pnl": baseline_8040_cents(trade),
                    "hypothetical_pnl_b": hyp_b,
                    "delta_vs_hold": None if hyp_b is None else hyp_b - hold,
                    "scenario_label": SCENARIO_LABEL,
                    "fill_status": FILL_STATUS,
                    "won": trade.get("won"),
                    "entry_timestamp": trade.get("entry_timestamp"),
                    "intervention_clock": None if chosen is None else chosen.get("game_clock_remaining"),
                    "intervention_period": None if chosen is None else chosen.get("period"),
                    "intervention_price": None if chosen is None else chosen.get("current_price_cents"),
                    "conditional_ev": None if chosen is None else chosen.get("conditional_ev_cents"),
                    "ci_lower": None if chosen is None else chosen.get("ci_lower_cents"),
                    "ci_upper": None if chosen is None else chosen.get("ci_upper_cents"),
                }
            )
            if action == "INTERVENE" and chosen is not None:
                future_prices = [int(r["current_price_cents"]) for r in later if r.get("current_price_cents") is not None]
                mfe = None if not future_prices else max(future_prices) - int(chosen.get("current_price_cents") or 0)
                mae = None if not future_prices else int(chosen.get("current_price_cents") or 0) - min(future_prices)
                winner = bool(trade.get("won"))
                interventions.append(
                    {
                        "trade_id": trade["trade_id"],
                        "policy_id": policy_id,
                        "checkpoint": chosen.get("timestamp_utc"),
                        "period": chosen.get("period"),
                        "game_clock_remaining": chosen.get("game_clock_remaining"),
                        "austin_ev": chosen.get("conditional_ev_cents"),
                        "ci_lower": chosen.get("ci_lower_cents"),
                        "ci_upper": chosen.get("ci_upper_cents"),
                        "market_price": chosen.get("current_price_cents"),
                        "future_mfe": mfe,
                        "future_mae": mae,
                        "maximum_future_favorable_price": None if not future_prices else max(future_prices),
                        "eventual_outcome": "WIN" if winner else "LOSS",
                        "baseline_pnl": hold,
                        "scenario_intervention_pnl": hyp_b,
                        "cents_sacrificed": None if (not winner or hyp_b is None) else max(0, hold - hyp_b),
                        "cents_saved": None if (winner or hyp_b is None) else max(0, hyp_b - hold),
                        "winner_abandoned": winner,
                        "loss_avoided": (not winner),
                        "scenario_label": SCENARIO_LABEL,
                    }
                )
    return ledgers, interventions


def persist_ledgers(
    experiment_id: str,
    cohort: str,
    trades: list[dict[str, Any]],
    queries: list[dict[str, Any]],
    *,
    policy_ids: list[str],
) -> dict[str, Path]:
    root = experiment_dir(experiment_id) / cohort.lower()
    hold = hold_rows(trades)
    eight = choosin_8040_rows(trades)
    policies, interventions = policy_rows(trades, queries, policy_ids=policy_ids)
    hold_fields = ["trade_id", "internal_game_id", "ledger", "won", "t40", "pnl_cents", "entry_timestamp"]
    _write(root / "baseline_hold_ledger.csv", hold, hold_fields)
    _write(root / "baseline_8040_ledger.csv", eight, hold_fields)
    policy_fields = list(policies[0].keys()) if policies else ["trade_id", "policy_id", "intervention"]
    _write(root / "policy_ledger.csv", policies, policy_fields)
    inter_fields = list(interventions[0].keys()) if interventions else ["trade_id", "policy_id"]
    _write(root / "intervention_ledger.csv", interventions, inter_fields)
    parent = experiment_dir(experiment_id)
    if cohort == "DISCOVERY":
        _write(parent / "baseline_hold_ledger.csv", hold, hold_fields)
        _write(parent / "baseline_8040_ledger.csv", eight, hold_fields)
        _write(parent / "policy_ledger.csv", policies, policy_fields)
        _write(parent / "intervention_ledger.csv", interventions, inter_fields)
    if cohort == "CONFIRMATION":
        _write(parent / "confirmation_baseline_hold_ledger.csv", hold, hold_fields)
        _write(parent / "confirmation_baseline_8040_ledger.csv", eight, hold_fields)
        _write(parent / "confirmation_policy_ledger.csv", policies, policy_fields)
        _write(parent / "confirmation_intervention_ledger.csv", interventions, inter_fields)
    return {"hold": root / "baseline_hold_ledger.csv", "policy": root / "policy_ledger.csv"}


def unused_policy_family() -> dict[str, Any]:
    return POLICY_FAMILY
