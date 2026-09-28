"""First-entry state economics and predeclared contrasts. A and B stay separate."""

from __future__ import annotations

from typing import Any

import numpy as np

from roller.austin.experiments.downfall.ids import (
    BOOTSTRAP_B,
    BOOTSTRAP_SEED,
    CONTRASTS,
    ORDERED_STATES,
    RISK_STATES,
)
from roller.austin.experiments.statistics import clustered_mean_diff


def _mean(values: list[Any]) -> float | None:
    nums = [float(v) for v in values if v is not None]
    return None if not nums else float(np.mean(nums))


def _median(values: list[Any]) -> float | None:
    nums = [float(v) for v in values if v is not None]
    return None if not nums else float(np.median(nums))


def _status(ci: dict[str, Any], *, n_a: int, n_b: int) -> str:
    if n_a < 2 or n_b < 2:
        return "INSUFFICIENT_SAMPLE"
    if ci.get("observed_delta") is None:
        return "INSUFFICIENT_SAMPLE"
    if ci.get("excludes_zero"):
        return "SUPPORTED"
    return "MIXED"


def summarize_entries(entries: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(entries)
    wins = sum(1 for e in entries if e.get("won"))
    losses = n - wins
    pnl = [e.get("OUTCOME_pnl_hold_after_state") for e in entries]
    mae = [e.get("OUTCOME_future_MAE") for e in entries]
    mfe = [e.get("OUTCOME_future_MFE") for e in entries]

    def rate(key: str) -> float | None:
        known = [e for e in entries if e.get(key) is not None]
        if not known:
            return None
        return sum(1 for e in known if e.get(key)) / len(known)

    return {
        "N_trades": n,
        "N_wins": wins,
        "N_losses": losses,
        "win_rate": None if not n else wins / n,
        "loss_rate": None if not n else losses / n,
        "mean_pnl_hold_after_state": _mean(pnl),
        "median_pnl_hold_after_state": _median(pnl),
        "T40_rate": rate("OUTCOME_future_T40"),
        "mean_future_MAE": _mean(mae),
        "mean_future_MFE": _mean(mfe),
        "recover_ge_50": rate("OUTCOME_recover_ge_50"),
        "recover_ge_60": rate("OUTCOME_recover_ge_60"),
        "recover_ge_70": rate("OUTCOME_recover_ge_70"),
        "recover_ge_80": rate("OUTCOME_recover_ge_80"),
        "mean_current_price": _mean([e.get("current_price") for e in entries]),
        "mean_price_travel": _mean([e.get("price_travel") for e in entries]),
        "mean_minutes_to_T40": _mean([e.get("OUTCOME_minutes_to_T40") for e in entries]),
        "mean_minutes_to_worst_price": _mean([e.get("OUTCOME_minutes_to_worst_price") for e in entries]),
        "mean_minutes_to_settlement": _mean([e.get("OUTCOME_minutes_to_settlement") for e in entries]),
        "mean_adverse_cents_remaining": _mean([e.get("adverse_cents_remaining") for e in entries]),
    }


def state_populations(timeline: list[dict[str, Any]], entries: list[dict[str, Any]], n_discovery: int) -> list[dict[str, Any]]:
    out = []
    for state in RISK_STATES:
        n_rows = sum(1 for r in timeline if r["core_state"] == state)
        n_trades = sum(1 for r in entries if r["core_state"] == state)
        out.append(
            {
                "core_state": state,
                "N_state_rows": n_rows,
                "N_trades_entering": n_trades,
                "pct_discovery_trades": None if not n_discovery else n_trades / n_discovery,
            }
        )
    return out


def state_economics(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for state in RISK_STATES:
        group = [e for e in entries if e["core_state"] == state]
        row = summarize_entries(group)
        row["core_state"] = state
        out.append(row)
    return out


def state_contrasts(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for left, right in CONTRASTS:
        rows = [e for e in entries if e["core_state"] in {left, right}]
        for key, name in (
            ("OUTCOME_pnl_hold_after_state", "pnl"),
            ("_loss", "loss_rate"),
            ("OUTCOME_future_MAE", "mae"),
            ("OUTCOME_future_MFE", "mfe"),
            ("_r80", "recover_ge_80"),
        ):
            labeled = []
            for row in rows:
                item = dict(row)
                item["_loss"] = 0.0 if row.get("won") else 1.0
                item["_r80"] = 1.0 if row.get("OUTCOME_recover_ge_80") else 0.0
                labeled.append(item)
            ci = clustered_mean_diff(
                labeled,
                value_key=key if key not in {"_loss", "_r80"} else key,
                positive_pred=lambda r, s=left: r["core_state"] == s,
                negative_pred=lambda r, s=right: r["core_state"] == s,
                seed=BOOTSTRAP_SEED,
                draws=BOOTSTRAP_B,
            )
            n_left = sum(1 for r in rows if r["core_state"] == left)
            n_right = sum(1 for r in rows if r["core_state"] == right)
            out.append(
                {
                    "contrast": f"{left} vs {right}",
                    "left_state": left,
                    "right_state": right,
                    "metric": name,
                    "n_left": n_left,
                    "n_right": n_right,
                    "observed_delta": ci.get("observed_delta"),
                    "ci": ci.get("ci"),
                    "classification": _status(ci, n_a=n_left, n_b=n_right),
                }
            )
    return out


def ordering_status(economics: list[dict[str, Any]]) -> dict[str, Any]:
    by_state = {r["core_state"]: r for r in economics}
    seq = [by_state.get(s) for s in ORDERED_STATES]
    if any(r is None or not r.get("N_trades") for r in seq):
        return {
            "classification": "INSUFFICIENT_SAMPLE",
            "monotonic": False,
            "note": "Missing ordered-state sample.",
        }

    def series(key: str, *, higher_worse: bool) -> list[float | None]:
        return [r.get(key) for r in seq]

    checks = {
        "mean_pnl_hold_after_state": False,
        "loss_rate": True,
        "mean_future_MAE": True,
        "mean_future_MFE": False,
        "recover_ge_80": False,
    }
    mono = {}
    for key, higher_worse in checks.items():
        vals = [v for v in series(key, higher_worse=higher_worse) if v is not None]
        if len(vals) < 2:
            mono[key] = None
            continue
        if higher_worse:
            mono[key] = all(a <= b for a, b in zip(vals, vals[1:]))
        else:
            mono[key] = all(a >= b for a, b in zip(vals, vals[1:]))
    known = [v for v in mono.values() if v is not None]
    if not known:
        cls = "INSUFFICIENT_SAMPLE"
    elif all(known):
        cls = "SUPPORTED"
    elif any(known):
        cls = "MIXED"
    else:
        cls = "NOT_SUPPORTED"
    return {
        "classification": cls,
        "monotonic": bool(known) and all(known),
        "by_metric": mono,
        "note": None if all(known) else "REPORT NOT MONOTONIC",
    }


POP_FIELDS = ["source_experiment_id", "core_state", "N_state_rows", "N_trades_entering", "pct_discovery_trades"]
ECON_FIELDS = [
    "source_experiment_id",
    "core_state",
    "N_trades",
    "N_wins",
    "N_losses",
    "win_rate",
    "loss_rate",
    "mean_pnl_hold_after_state",
    "median_pnl_hold_after_state",
    "T40_rate",
    "mean_future_MAE",
    "mean_future_MFE",
    "recover_ge_50",
    "recover_ge_60",
    "recover_ge_70",
    "recover_ge_80",
    "mean_current_price",
    "mean_price_travel",
    "mean_minutes_to_worst_price",
    "mean_minutes_to_settlement",
    "mean_adverse_cents_remaining",
]
CONTRAST_FIELDS = [
    "source_experiment_id",
    "contrast",
    "left_state",
    "right_state",
    "metric",
    "n_left",
    "n_right",
    "observed_delta",
    "ci_lo",
    "ci_hi",
    "classification",
]


def flatten_contrasts(experiment_id: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        ci = row.get("ci") or [None, None]
        out.append(
            {
                "source_experiment_id": experiment_id,
                **row,
                "ci_lo": None if not ci else ci[0],
                "ci_hi": None if not ci else ci[1],
            }
        )
    return out
